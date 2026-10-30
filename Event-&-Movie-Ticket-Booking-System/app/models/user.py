from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    phone = Column(String(10), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_approved = Column(Boolean, nullable=False, default=False)      # used for Organizers
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=True)  # used for Staff

    venue = relationship("Venue", back_populates="staff")
    events = relationship("Event", back_populates="organizer")
    bookings = relationship("Booking", back_populates="customer")
