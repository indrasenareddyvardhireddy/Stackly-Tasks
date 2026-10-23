from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import TimestampMixin


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    label = Column(String(20), nullable=False)  # Home | Work | Other
    address_line = Column(String(255), nullable=False)
    city = Column(String(80), nullable=False)
    pincode = Column(String(6), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    customer = relationship("User", back_populates="addresses")


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    coupon_id = Column(Integer, ForeignKey("coupons.id"))

    customer = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    coupon = relationship("Coupon")


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "menu_item_id", name="uq_cart_item"),)
    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)

    cart = relationship("Cart", back_populates="items")
    menu_item = relationship("MenuItem")
