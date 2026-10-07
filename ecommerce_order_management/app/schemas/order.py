from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel

from app.models.order import (
    OrderStatus,
    PaymentStatus
)


# =========================================================
# ORDER ITEM RESPONSE
# =========================================================

class OrderItemResponse(BaseModel):

    product_id: int

    quantity: int

    unit_price: Decimal

    line_total: Decimal

    model_config = {
        "from_attributes": True
    }


# =========================================================
# ORDER RESPONSE
# =========================================================

class OrderResponse(BaseModel):

    id: int

    order_number: str

    customer_id: int

    address_id: int

    # Original cart subtotal
    subtotal: Decimal

    # Coupon discount
    discount_amount: Decimal

    # GST amount
    tax_amount: Decimal

    # Delivery charge
    delivery_charge: Decimal

    # Final amount customer needs to pay
    grand_total: Decimal

    status: OrderStatus

    payment_status: PaymentStatus

    delivered_at: datetime | None

    items: list[OrderItemResponse] = []

    model_config = {
        "from_attributes": True
    }


# =========================================================
# ORDER STATUS UPDATE
# =========================================================

class OrderStatusUpdate(BaseModel):

    status: OrderStatus