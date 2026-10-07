from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderResponse, OrderStatusUpdate
from app.services.order_service import (
    create_order,
    cancel_order,
    update_order_status
)
from app.utils.email import send_email
from app.auth.dependencies import require_role


router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


# =========================================================
# PLACE ORDER
# =========================================================

@router.post(
    "",
    response_model=OrderResponse,
    status_code=201
)
def place(
    address_id: int,
    coupon_code: str | None = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role(UserRole.Customer)
    )
):
    """
    Place an order from the customer's cart.

    address_id:
        Required customer's address ID.

    coupon_code:
        Optional coupon code.

    Example:
        POST /orders?address_id=1&coupon_code=Offer1
    """

    order = create_order(
        db=db,
        user=user,
        address_id=address_id,
        coupon_code=coupon_code
    )

    # -----------------------------------------------------
    # Send order confirmation email
    # -----------------------------------------------------

    background_tasks.add_task(
        send_email,
        user.email,
        "Order placed",
        (
            f"Order {order.order_number} placed successfully.\n\n"
            f"Subtotal: ₹{order.subtotal}\n"
            f"Discount: ₹{order.discount_amount}\n"
            f"Tax: ₹{order.tax_amount}\n"
            f"Delivery: ₹{order.delivery_charge}\n"
            f"Grand Total: ₹{order.grand_total}"
        )
    )

    return order


# =========================================================
# LIST ORDERS
# =========================================================

@router.get(
    "",
    response_model=list[OrderResponse]
)
def list_orders(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role(
            UserRole.Admin,
            UserRole.Customer
        )
    )
):
    """
    Admin:
        View all orders.

    Customer:
        View only their own orders.
    """

    q = (
        select(Order)
        .options(
            selectinload(Order.items)
        )
    )

    # -----------------------------------------------------
    # Customer can only see own orders
    # -----------------------------------------------------

    if user.role == UserRole.Customer:
        q = q.where(
            Order.customer_id == user.id
        )

    return (
        db.scalars(
            q.offset(skip).limit(limit)
        )
        .unique()
        .all()
    )


# =========================================================
# GET SINGLE ORDER
# =========================================================

@router.get(
    "/{order_id}",
    response_model=OrderResponse
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role(
            UserRole.Admin,
            UserRole.Customer
        )
    )
):
    """
    Admin:
        Can view any order.

    Customer:
        Can view only their own order.
    """

    q = (
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(
            Order.id == order_id
        )
    )

    # -----------------------------------------------------
    # Customer ownership restriction
    # -----------------------------------------------------

    if user.role == UserRole.Customer:
        q = q.where(
            Order.customer_id == user.id
        )

    order = db.scalar(q)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return order


# =========================================================
# CANCEL ORDER
# =========================================================

@router.put(
    "/{order_id}/cancel",
    response_model=OrderResponse
)
def cancel(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role(
            UserRole.Admin,
            UserRole.Customer
        )
    )
):
    """
    Cancel an order.

    Only Pending or Confirmed orders can be cancelled.
    """

    order = cancel_order(
        db,
        user,
        order_id
    )

    # -----------------------------------------------------
    # Cancellation email
    # -----------------------------------------------------

    background_tasks.add_task(
        send_email,
        user.email,
        "Order cancelled",
        (
            f"Order {order.order_number} "
            f"was cancelled successfully."
        )
    )

    return order


# =========================================================
# UPDATE ORDER STATUS - ADMIN ONLY
# =========================================================

@router.put(
    "/{order_id}/status",
    response_model=OrderResponse
)
def status(
    order_id: int,
    data: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role(UserRole.Admin)
    )
):
    """
    Admin only.

    Allowed status flow:

    Pending
        ↓
    Confirmed
        ↓
    Shipped
        ↓
    Delivered
    """

    order = update_order_status(
        db,
        order_id,
        data.status
    )

    # -----------------------------------------------------
    # Shipping email
    # -----------------------------------------------------

    if data.status == OrderStatus.Shipped:

        background_tasks.add_task(
            send_email,
            order.customer.email,
            "Order shipped",
            (
                f"Order {order.order_number} "
                f"has been shipped."
            )
        )

    # -----------------------------------------------------
    # Delivery email
    # -----------------------------------------------------

    if data.status == OrderStatus.Delivered:

        background_tasks.add_task(
            send_email,
            order.customer.email,
            "Order delivered",
            (
                f"Order {order.order_number} "
                f"has been delivered."
            )
        )

    return order