from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import Money, TimestampMixin


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, nullable=False, index=True)  # stored upper-case
    description = Column(String(255))
    discount_type = Column(String(20), nullable=False)  # Percentage | Flat
    discount_value = Column(Float, nullable=False)
    max_discount = Column(Money)
    min_order_value = Column(Money, default=0, nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))  # NULL = platform-wide
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    total_usage_limit = Column(Integer)
    per_user_limit = Column(Integer)
    first_order_only = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    restaurant = relationship("Restaurant", back_populates="coupons")
    usages = relationship("CouponUsage", back_populates="coupon")


class CouponUsage(Base, TimestampMixin):
    __tablename__ = "coupon_usages"
    id = Column(Integer, primary_key=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    discount_amount = Column(Money, nullable=False)
    is_released = Column(Boolean, default=False, nullable=False)
    released_at = Column(DateTime)

    coupon = relationship("Coupon", back_populates="usages")
