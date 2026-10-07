from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Numeric,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.database import Base


# =========================================================
# ORDER STATUS
# =========================================================

class OrderStatus(str, enum.Enum):

    Pending = "Pending"

    Confirmed = "Confirmed"

    Shipped = "Shipped"

    Delivered = "Delivered"

    Cancelled = "Cancelled"


# =========================================================
# PAYMENT STATUS
# =========================================================

class PaymentStatus(str, enum.Enum):

    Unpaid = "Unpaid"

    Paid = "Paid"

    Refunded = "Refunded"


# =========================================================
# ORDER
# =========================================================

class Order(Base):

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    order_number: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        index=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id"),
        nullable=False
    )

    # =====================================================
    # COUPON
    # =====================================================

    coupon_id: Mapped[int | None] = mapped_column(
        ForeignKey("coupons.id"),
        nullable=True
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00")
    )

    # =====================================================
    # ORDER AMOUNTS
    # =====================================================

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    delivery_charge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    grand_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    # =====================================================
    # STATUS
    # =====================================================

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.Pending
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.Unpaid
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    customer = relationship(
        "User",
        back_populates="orders"
    )

    address = relationship(
        "Address",
        back_populates="orders"
    )

    coupon = relationship(
        "Coupon",
        back_populates="orders"
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    payments = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    return_request = relationship(
        "ReturnRequest",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )


# =========================================================
# ORDER ITEM
# =========================================================

class OrderItem(Base):

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    order = relationship(
        "Order",
        back_populates="items"
    )

    product = relationship(
        "Product",
        back_populates="order_items"
    )