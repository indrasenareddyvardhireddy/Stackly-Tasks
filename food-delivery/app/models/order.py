from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import Money, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(String(30), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    delivery_partner_id = Column(Integer, ForeignKey("delivery_partners.id"))
    item_total = Column(Money, nullable=False)
    coupon_code = Column(String(40))
    discount_amount = Column(Money, default=0, nullable=False)
    packaging_charges = Column(Money, default=0, nullable=False)
    delivery_fee = Column(Money, nullable=False)
    platform_fee = Column(Money, nullable=False)
    gst_amount = Column(Money, nullable=False)
    tip_amount = Column(Money, default=0, nullable=False)
    grand_total = Column(Money, nullable=False)
    payment_method = Column(String(10), nullable=False)   # COD | Online
    payment_status = Column(String(10), nullable=False)   # Pending | Paid | Refunded
    status = Column(String(30), nullable=False, index=True)
    distance_km = Column(Float, nullable=False)
    delivery_otp = Column(String(4), nullable=False)
    otp_attempts = Column(Integer, default=0, nullable=False)
    delivery_locked = Column(Boolean, default=False, nullable=False)
    estimated_prep_minutes = Column(Integer)
    rejection_reason = Column(String(255))
    admin_notified_unassigned = Column(Boolean, default=False, nullable=False)
    placed_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)
    ready_at = Column(DateTime)
    delivered_at = Column(DateTime)

    customer = relationship("User", back_populates="orders", foreign_keys=[customer_id])
    restaurant = relationship("Restaurant", back_populates="orders")
    address = relationship("Address")
    partner = relationship("DeliveryPartner")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan",
                           order_by="OrderStatusHistory.id")
    offers = relationship("DeliveryOffer", back_populates="order")
    delivery = relationship("Delivery", back_populates="order", uselist=False)
    rating = relationship("Rating", back_populates="order", uselist=False)


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    item_name = Column(String(150), nullable=False)
    price = Column(Money, nullable=False)              # price at time of order
    packaging_charge = Column(Money, default=0, nullable=False)
    quantity = Column(Integer, nullable=False)
    line_total = Column(Money, nullable=False)

    order = relationship("Order", back_populates="items")


class OrderStatusHistory(Base, TimestampMixin):
    __tablename__ = "order_status_history"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    old_status = Column(String(30))
    new_status = Column(String(30), nullable=False)
    changed_by = Column(String(100), nullable=False)   # "System" or "<role>:<user_id>"
    note = Column(String(255))
    changed_at = Column(DateTime, nullable=False)

    order = relationship("Order", back_populates="history")


class DeliveryOffer(Base, TimestampMixin):
    __tablename__ = "delivery_offers"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey("delivery_partners.id"), nullable=False, index=True)
    status = Column(String(10), default="Pending", nullable=False)  # Pending|Accepted|Declined|Expired
    offered_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    order = relationship("Order", back_populates="offers")
    partner = relationship("DeliveryPartner", back_populates="offers")


class Delivery(Base, TimestampMixin):
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    partner_id = Column(Integer, ForeignKey("delivery_partners.id"), nullable=False, index=True)
    status = Column(String(10), default="Active", nullable=False)  # Active | Completed
    distance_km = Column(Float, nullable=False)
    earnings = Column(Money, default=0, nullable=False)
    assigned_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)

    order = relationship("Order", back_populates="delivery")
    partner = relationship("DeliveryPartner", back_populates="deliveries")


class Rating(Base, TimestampMixin):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey("delivery_partners.id"))
    restaurant_rating = Column(Integer, nullable=False)
    partner_rating = Column(Integer, nullable=False)
    comment = Column(Text)

    order = relationship("Order", back_populates="rating")


class Notification(Base, TimestampMixin):
    """Admin / user notifications (e.g. unassigned order, OTP lock)."""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    target_role = Column(String(30), nullable=False, default="admin")
    user_id = Column(Integer, ForeignKey("users.id"))
    order_id = Column(Integer, ForeignKey("orders.id"))
    message = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
