import logging
from datetime import timedelta
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.booking import BookedSeat, Booking
from app.models.enums import BookingStatus
from app.models.event import Show
from app.models.user import User
from app.models.venue import Seat
from app.redis_client import redis_client as r
from app.services import seat_service
from app.utils.billing import calculate_bill, money
from app.utils.time import now

logger = logging.getLogger(__name__)


def booking_context(booking: Booking) -> dict:
    """Plain-dict snapshot of a booking for emails / PDF (safe to use after the session closes)."""
    show = booking.show
    return {
        "booking_id": booking.id,
        "booking_number": booking.booking_number,
        "customer_id": booking.customer_id,
        "customer_name": booking.customer.name,
        "customer_email": booking.customer.email,
        "event_title": show.event.title,
        "venue_name": show.screen.venue.name,
        "screen_name": show.screen.name,
        "show_id": show.id,
        "show_datetime": show.start_at.strftime("%d %b %Y, %I:%M %p"),
        "seats": ", ".join(bs.label for bs in booking.seats),
        "seat_count": booking.seat_count,
        "amount": str(booking.grand_total),
        "ticket_total": str(booking.ticket_total),
    }


def _next_booking_number(db: Session) -> str:
    day = now().strftime("%Y%m%d")
    key = f"seq:booking:{day}"
    while True:
        seq = r.incr(key)
        r.expire(key, 3 * 86400)
        number = f"BKG-{day}-{seq:04d}"
        if not db.query(Booking.id).filter(Booking.booking_number == number).first():
            return number


def create_booking(db: Session, show: Show, user: User, seat_ids: List[int]) -> Booking:
    seat_service.ensure_show_open(show)
    seat_ids = list(dict.fromkeys(seat_ids))

    seats = db.query(Seat).filter(Seat.id.in_(seat_ids), Seat.screen_id == show.screen_id).all()
    if len(seats) != len(seat_ids):
        raise HTTPException(status_code=404, detail="One or more seats do not belong to this show's screen")
    seat_by_id = {s.id: s for s in seats}

    owners = seat_service.get_lock_owners(show.id, seat_ids)
    not_mine = [seat_by_id[sid].label for sid in seat_ids if owners.get(sid) != user.id]
    if not_mine:
        raise HTTPException(status_code=409, detail=(
            f"Seats {', '.join(not_mine)} are not locked by you (lock them first, or your lock expired)"))

    # a seat can belong to only one pending booking; stale (expired) pending bookings are closed here
    pending = (db.query(Booking).join(BookedSeat, BookedSeat.booking_id == Booking.id)
               .filter(Booking.show_id == show.id, Booking.status == BookingStatus.PENDING.value,
                       BookedSeat.seat_id.in_(seat_ids)).distinct().all())
    for p in pending:
        if p.expires_at and p.expires_at < now():
            p.status = BookingStatus.EXPIRED.value
        else:
            raise HTTPException(status_code=409, detail=(
                f"A pending booking ({p.booking_number}) already exists for some of these seats"))
    db.flush()

    ttls = [r.ttl(seat_service.lock_key(show.id, sid)) for sid in seat_ids]
    ttl = min([t for t in ttls if t and t > 0] or [1])

    base_prices = seat_service.get_base_prices(db, show.id)
    mult = seat_service.current_multiplier(db, show)
    seat_prices = {}
    for sid in seat_ids:
        base = base_prices.get(seat_by_id[sid].category)
        if base is None:
            raise HTTPException(status_code=400, detail=f"No price set for category {seat_by_id[sid].category}")
        seat_prices[sid] = money(base * mult)

    bill = calculate_bill(seat_prices.values())
    booking = Booking(
        booking_number=_next_booking_number(db),
        customer_id=user.id,
        show_id=show.id,
        seat_count=bill["seat_count"],
        ticket_total=bill["ticket_total"],
        convenience_fee=bill["convenience_fee"],
        gst_amount=bill["gst_amount"],
        grand_total=bill["grand_total"],
        status=BookingStatus.PENDING.value,
        expires_at=now() + timedelta(seconds=ttl),   # matches the lock expiry
    )
    db.add(booking)
    db.flush()
    for sid in seat_ids:
        db.add(BookedSeat(booking_id=booking.id, show_id=show.id, seat_id=sid, price=seat_prices[sid]))
    db.commit()
    db.refresh(booking)
    return booking
