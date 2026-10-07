from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import settings

from app.models.cart import Cart
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
)
from app.models.product import Product
from app.models.address import Address
from app.models.payment import (
    Payment,
    PaymentMethod,
    PaymentResult,
)
from app.models.user import User
from app.models.return_request import (
    ReturnRequest,
    ReturnStatus,
)
from app.models.coupon import Coupon


def money(value):
    """
    Convert a value to Decimal with 2 decimal places.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def create_order(
    db: Session,
    user: User,
    address_id: int,
    coupon_code: str | None = None,
):
    """
    Create an order from the customer's cart.

    Order calculation:

        Cart subtotal
             ↓
        Coupon discount
             ↓
        Discounted subtotal
             ↓
        GST
             ↓
        Delivery charge
             ↓
        Grand total
    """

    # ---------------------------------------------------------
    # 1. Validate customer's address
    # ---------------------------------------------------------

    address = db.scalar(
        select(Address).where(
            Address.id == address_id,
            Address.customer_id == user.id
        )
    )

    if not address:
        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    # ---------------------------------------------------------
    # 2. Get customer's cart
    # ---------------------------------------------------------

    cart = db.scalar(
        select(Cart).where(
            Cart.customer_id == user.id
        )
    )

    if not cart or not cart.items:
        raise HTTPException(
            status_code=400,
            detail="Cannot place an order with an empty cart"
        )

    # ---------------------------------------------------------
    # 3. Start transaction
    # ---------------------------------------------------------

    try:

        subtotal = Decimal("0.00")
        order_items = []

        # -----------------------------------------------------
        # 4. Validate products and calculate subtotal
        # -----------------------------------------------------

        for cart_item in list(cart.items):

            product = db.execute(
                select(Product)
                .where(Product.id == cart_item.product_id)
                .with_for_update()
            ).scalar_one()

            # Product must be active
            if not product.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product {product.name} is inactive"
                )

            # Product must have sufficient stock
            if product.stock_quantity < cart_item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product.name}"
                )

            # Calculate line total
            line_total = money(
                product.price * cart_item.quantity
            )

            subtotal += line_total

            order_items.append(
                (
                    product,
                    cart_item.quantity,
                    product.price,
                    line_total
                )
            )

        subtotal = money(subtotal)

        # -----------------------------------------------------
        # 5. Apply coupon
        # -----------------------------------------------------

        discount_amount = Decimal("0.00")
        coupon = None

        if coupon_code:

            # Remove accidental spaces
            coupon_code = coupon_code.strip()

            # Find coupon
            coupon = db.scalar(
                select(Coupon)
                .where(Coupon.code == coupon_code)
                .with_for_update()
            )

            if not coupon:
                raise HTTPException(
                    status_code=404,
                    detail="Invalid coupon code"
                )

            # -------------------------------------------------
            # Check expiry
            # -------------------------------------------------

            now = datetime.now(timezone.utc)

            expires_at = coupon.expires_at

            # Handle MySQL datetime without timezone
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            if expires_at <= now:
                raise HTTPException(
                    status_code=400,
                    detail="Coupon has expired"
                )

            # -------------------------------------------------
            # Check minimum order value
            # -------------------------------------------------

            if subtotal < Decimal(
                str(coupon.minimum_order_value)
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Minimum order value for this coupon "
                        f"is ₹{coupon.minimum_order_value}"
                    )
                )

            # -------------------------------------------------
            # Check usage limit
            # -------------------------------------------------

            if coupon.usage_limit is not None:

                current_usage = getattr(
                    coupon,
                    "used_count",
                    0
                )

                if current_usage >= coupon.usage_limit:
                    raise HTTPException(
                        status_code=400,
                        detail="Coupon usage limit reached"
                    )

            # -------------------------------------------------
            # Calculate percentage discount
            # -------------------------------------------------

            if coupon.coupon_type == "Percentage":

                discount_amount = money(
                    subtotal
                    * Decimal(str(coupon.value))
                    / Decimal("100")
                )

            # -------------------------------------------------
            # Calculate flat discount
            # -------------------------------------------------

            elif coupon.coupon_type == "Flat":

                discount_amount = money(
                    coupon.value
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid coupon type"
                )

            # Discount cannot exceed subtotal
            if discount_amount > subtotal:
                discount_amount = subtotal

        # -----------------------------------------------------
        # 6. Calculate discounted subtotal
        # -----------------------------------------------------

        discounted_subtotal = money(
            subtotal - discount_amount
        )

        # -----------------------------------------------------
        # 7. Calculate GST
        #
        # GST is calculated after coupon discount.
        # -----------------------------------------------------

        tax = money(
            discounted_subtotal
            * Decimal(str(settings.GST_RATE))
            / Decimal("100")
        )

        # -----------------------------------------------------
        # 8. Calculate delivery charge
        # -----------------------------------------------------

        if discounted_subtotal > Decimal(
            str(settings.FREE_DELIVERY_THRESHOLD)
        ):
            delivery = Decimal("0.00")
        else:
            delivery = Decimal(
                str(settings.DELIVERY_CHARGE)
            )

        delivery = money(delivery)

        # -----------------------------------------------------
        # 9. Calculate grand total
        # -----------------------------------------------------

        total = money(
            discounted_subtotal
            + tax
            + delivery
        )

        # -----------------------------------------------------
        # 10. Generate order number
        # -----------------------------------------------------

        today = datetime.utcnow().strftime("%Y%m%d")

        latest_order = db.scalar(
            select(Order.id)
            .where(
                Order.order_number.like(
                    f"ORD-{today}-%"
                )
            )
            .order_by(Order.id.desc())
            .limit(1)
        )

        seq = (latest_order or 0) + 1

        order_number = (
            f"ORD-{today}-{seq:04d}"
        )

        # -----------------------------------------------------
        # 11. Create order
        # -----------------------------------------------------

        order = Order(
            order_number=order_number,
            customer_id=user.id,
            address_id=address_id,

            # Coupon information
            coupon_id=coupon.id if coupon else None,
            discount_amount=discount_amount,

            subtotal=subtotal,
            tax_amount=tax,
            delivery_charge=delivery,
            grand_total=total,

            status=OrderStatus.Pending,
            payment_status=PaymentStatus.Unpaid
        )

        db.add(order)

        # Get generated order ID
        db.flush()

        # -----------------------------------------------------
        # 12. Reduce product stock
        # -----------------------------------------------------

        for product, quantity, unit_price, line_total in order_items:

            product.stock_quantity -= quantity

            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total
                )
            )

        # -----------------------------------------------------
        # 13. Increase coupon usage
        # -----------------------------------------------------

        if coupon:

            if hasattr(coupon, "used_count"):
                coupon.used_count += 1

        # -----------------------------------------------------
        # 14. Clear customer's cart
        # -----------------------------------------------------

        for cart_item in list(cart.items):
            db.delete(cart_item)

        # -----------------------------------------------------
        # 15. Commit everything
        # -----------------------------------------------------

        db.commit()

        # -----------------------------------------------------
        # 16. Refresh order
        # -----------------------------------------------------

        db.refresh(order)

        return order

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise


def cancel_order(
    db: Session,
    user: User,
    order_id: int
):
    """
    Cancel Pending or Confirmed orders.

    Stock is restored when the order is cancelled.
    Paid orders are marked as Refunded.
    """

    q = select(Order).where(
        Order.id == order_id
    )

    if user.role.value == "Customer":

        q = q.where(
            Order.customer_id == user.id
        )

    order = db.scalar(q)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # ---------------------------------------------------------
    # Only Pending and Confirmed orders can be cancelled
    # ---------------------------------------------------------

    if order.status not in [
        OrderStatus.Pending,
        OrderStatus.Confirmed
    ]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only Pending or Confirmed orders "
                "can be cancelled"
            )
        )

    try:

        # -----------------------------------------------------
        # Restore product stock
        # -----------------------------------------------------

        for item in order.items:

            product = db.execute(
                select(Product)
                .where(Product.id == item.product_id)
                .with_for_update()
            ).scalar_one()

            product.stock_quantity += item.quantity

        # -----------------------------------------------------
        # Update order status
        # -----------------------------------------------------

        order.status = OrderStatus.Cancelled

        # -----------------------------------------------------
        # Refund if already paid
        # -----------------------------------------------------

        if order.payment_status == PaymentStatus.Paid:
            order.payment_status = PaymentStatus.Refunded

        db.commit()

        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus
):
    """
    Update order status according to the allowed
    forward status transitions.
    """

    order = db.get(
        Order,
        order_id
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    transitions = {
        OrderStatus.Pending: [
            OrderStatus.Confirmed,
            OrderStatus.Cancelled
        ],

        OrderStatus.Confirmed: [
            OrderStatus.Shipped,
            OrderStatus.Cancelled
        ],

        OrderStatus.Shipped: [
            OrderStatus.Delivered
        ],

        OrderStatus.Delivered: [],

        OrderStatus.Cancelled: []
    }

    if new_status not in transitions[order.status]:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition "
                f"from {order.status.value} "
                f"to {new_status.value}"
            )
        )

    order.status = new_status

    # ---------------------------------------------------------
    # Delivered
    # ---------------------------------------------------------

    if new_status == OrderStatus.Delivered:

        order.delivered_at = datetime.utcnow()

        # COD becomes paid when delivered
        if any(
            payment.payment_method == PaymentMethod.COD
            and payment.status == PaymentResult.Success
            for payment in order.payments
        ):
            order.payment_status = PaymentStatus.Paid

    db.commit()

    db.refresh(order)

    return order