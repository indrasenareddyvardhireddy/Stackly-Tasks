from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(10), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)  # admin | restaurant_owner | delivery_partner | customer
    is_approved = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    restaurants = relationship("Restaurant", back_populates="owner")
    addresses = relationship("Address", back_populates="customer", cascade="all, delete-orphan")
    cart = relationship("Cart", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer", foreign_keys="Order.customer_id")
    partner_profile = relationship("DeliveryPartner", back_populates="user", uselist=False)


class DeliveryPartner(Base, TimestampMixin):
    __tablename__ = "delivery_partners"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    vehicle_type = Column(String(20), nullable=False)  # Bike | Scooter | Bicycle
    vehicle_number = Column(String(30), unique=True, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)
    current_latitude = Column(Float)
    current_longitude = Column(Float)
    last_location_at = Column(DateTime)
    is_approved = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="partner_profile")
    deliveries = relationship("Delivery", back_populates="partner")
    offers = relationship("DeliveryOffer", back_populates="partner")
