from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    category = Column(String(20), nullable=False)
    language = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    age_rating = Column(String(5), nullable=False)
    status = Column(String(20), nullable=False, default="Draft", index=True)

    organizer = relationship("User", back_populates="events")
    shows = relationship("Show", back_populates="event", cascade="all, delete-orphan")


class Show(TimestampMixin, Base):
    __tablename__ = "shows"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    screen_id = Column(Integer, ForeignKey("screens.id"), nullable=False)
    show_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)            # calculated from event duration
    start_at = Column(DateTime, nullable=False, index=True)   # show_date + start_time
    end_at = Column(DateTime, nullable=False)                 # start_at + duration (may cross midnight)
    booking_closes_at = Column(DateTime, nullable=False)      # start_at - 30 minutes
    status = Column(String(20), nullable=False, default="Scheduled")

    event = relationship("Event", back_populates="shows")
    screen = relationship("Screen", back_populates="shows")
    prices = relationship("SeatCategoryPrice", back_populates="show", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="show")
    waitlist = relationship("Waitlist", back_populates="show")

    @property
    def screen_name(self) -> str:
        return self.screen.name

    @property
    def venue_id(self) -> int:
        return self.screen.venue_id

    @property
    def venue_name(self) -> str:
        return self.screen.venue.name

    @property
    def city(self) -> str:
        return self.screen.venue.city


class SeatCategoryPrice(TimestampMixin, Base):
    __tablename__ = "seat_category_prices"
    __table_args__ = (UniqueConstraint("show_id", "category", name="uq_show_category_price"),)

    id = Column(Integer, primary_key=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    category = Column(String(20), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    show = relationship("Show", back_populates="prices")
