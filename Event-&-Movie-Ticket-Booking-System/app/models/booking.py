from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_number = Column(String(30), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    seat_count = Column(Integer, nullable=False)
    ticket_total = Column(Numeric(10, 2), nullable=False)
    convenience_fee = Column(Numeric(10, 2), nullable=False)
    gst_amount = Column(Numeric(10, 2), nullable=False)
    grand_total = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="Pending Payment", index=True)
    expires_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    reminder_sent = Column(Boolean, nullable=False, default=False)
    razorpay_order_id = Column(String(40), nullable=True, index=True)

    customer = relationship("User", back_populates="bookings")
    show = relationship("Show", back_populates="bookings")
    seats = relationship("BookedSeat", back_populates="booking", cascade="all, delete-orphan",
                         order_by="BookedSeat.id")
    payments = relationship("Payment", back_populates="booking", order_by="Payment.id")
    refunds = relationship("Refund", back_populates="booking", order_by="Refund.id")
    ticket = relationship("Ticket", back_populates="booking", uselist=False)

    # convenience read-only fields used by the response schemas
    @property
    def event_title(self) -> str:
        return self.show.event.title

    @property
    def venue_name(self) -> str:
        return self.show.screen.venue.name

    @property
    def screen_name(self) -> str:
        return self.show.screen.name

    @property
    def show_start(self):
        return self.show.start_at


class BookedSeat(TimestampMixin, Base):
    """
    A seat that belongs to a booking.

    `confirmed_seat_id` is NULL while the booking is pending / cancelled and equals `seat_id`
    once the booking is confirmed. The unique constraint on (show_id, confirmed_seat_id)
    therefore guarantees a seat can be confirmed only once per show (MySQL allows many NULLs
    in a unique index, so cancelled seats can be booked again).
    """
    __tablename__ = "booked_seats"
    __table_args__ = (UniqueConstraint("show_id", "confirmed_seat_id", name="uq_confirmed_seat_per_show"),)

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    confirmed_seat_id = Column(Integer, nullable=True)

    booking = relationship("Booking", back_populates="seats")
    seat = relationship("Seat")

    @property
    def row_label(self) -> str:
        return self.seat.row_label

    @property
    def seat_number(self) -> int:
        return self.seat.seat_number

    @property
    def category(self) -> str:
        return self.seat.category

    @property
    def label(self) -> str:
        return self.seat.label


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    transaction_id = Column(String(40), nullable=False, unique=True)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    paid_at = Column(DateTime, nullable=True)
    razorpay_order_id = Column(String(40), nullable=True)
    razorpay_payment_id = Column(String(40), nullable=True, unique=True)   # same gateway payment is processed once
    razorpay_signature = Column(String(200), nullable=True)

    booking = relationship("Booking", back_populates="payments")


class Refund(TimestampMixin, Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="Processed")
    refunded_at = Column(DateTime, nullable=False)

    booking = relationship("Booking", back_populates="refunds")


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    qr_value = Column(String(100), nullable=False)
    pdf_path = Column(String(255), nullable=True)
    is_used = Column(Boolean, nullable=False, default=False)
    used_at = Column(DateTime, nullable=True)
    scanned_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    booking = relationship("Booking", back_populates="ticket")
