from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    address = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    screens = relationship("Screen", back_populates="venue", cascade="all, delete-orphan")
    staff = relationship("User", back_populates="venue")


class Screen(TimestampMixin, Base):
    __tablename__ = "screens"

    id = Column(Integer, primary_key=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    name = Column(String(100), nullable=False)
    total_seats = Column(Integer, nullable=False, default=0)

    venue = relationship("Venue", back_populates="screens")
    seats = relationship("Seat", back_populates="screen", cascade="all, delete-orphan")
    shows = relationship("Show", back_populates="screen")


class Seat(TimestampMixin, Base):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("screen_id", "row_label", "seat_number", name="uq_seat_position"),)

    id = Column(Integer, primary_key=True)
    screen_id = Column(Integer, ForeignKey("screens.id"), nullable=False)
    row_label = Column(String(5), nullable=False)
    seat_number = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    screen = relationship("Screen", back_populates="seats")

    @property
    def label(self) -> str:
        return f"{self.row_label}{self.seat_number}"
