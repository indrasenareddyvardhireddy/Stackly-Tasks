from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import String, DateTime, Integer, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CouponType(str, enum.Enum):
    Percentage = "Percentage"
    Flat = "Flat"


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    coupon_type: Mapped[CouponType] = mapped_column(
        Enum(CouponType),
        nullable=False
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    minimum_order_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    usage_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    used_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
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

    orders = relationship(
        "Order",
        back_populates="coupon"
    )