"""Customer cancellation, organizer show cancellation and waitlist notification."""
import logging
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.booking import Booking, Payment, Refund
from app.models.enums import (REFUND_PROCESSED, BookingStatus, PaymentStatus, RefundReason,
                              ShowStatus, WaitlistStatus)
from app.models.event import Show
from app.models.user import User
from app.models.waitlist import Waitlist
from app.services import cache_service, email_service, seat_service
from app.services.booking_service import booking_context
from app.utils.billing import money
from app.utils.refund_policy import FULL_REFUND, refund_percentage
from app.utils.time import now
from app.websockets.manager import manager

logger = logging.getLogger(__name__)


def _mark_payment_refunded(booking: Booking):
    paid = [p for p in booking.payments if p.status == PaymentStatus.SUCCESS.value]
    payment: Optional[Payment] = paid[-1] if paid else None
    if payment:
        payment.status = PaymentStatus.REFUNDED.value
    return payment


def _free_seats(booking: Booking) -> List[dict]:
    """Seats become Available again immediately."""
    changes = []
    for bs in booking.seats:
        bs.confirmed_seat_id = None
        changes.append(seat_service.change(bs.seat, "Available"))
    return changes


# ---------------------------------------------------------------------------- customer cancellation
def cancel_booking(db: Session, booking_id: int, user: User, background_tasks) -> dict:
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if not booking or booking.customer_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    show = booking.show
    ctx = booking_context(booking)
    t = now()

    # --- pending booking: just give the seats back, nothing was paid
    if booking.status == BookingStatus.PENDING.value:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = t
        db.commit()
        changes = []
        for bs in booking.seats:
            if seat_service.release_lock_if_owner(booking.show_id, bs.seat_id, user.id):
                changes.append(seat_service.change(bs.seat, "Available"))
        manager.push_seat_changes(show.id, changes)
        return {"booking_number": booking.booking_number, "status": booking.status,
                "refund_amount": Decimal("0.00"), "refund_percentage": 0,
                "message": "Pending booking cancelled and seats released."}

    if booking.status != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Booking is already {booking.status}")

    hours_before = (show.start_at - t).total_seconds() / 3600
    pct = refund_percentage(hours_before)
    if pct is None:
        raise HTTPException(status_code=400, detail="Cancellation is not allowed less than 2 hours before the show")

    # convenience fee and its GST are NOT refunded on customer cancellations
    refund_amount = money(Decimal(booking.ticket_total) * pct)
    payment = _mark_payment_refunded(booking)
    db.add(Refund(booking_id=booking.id, payment_id=payment.id if payment else None, amount=refund_amount,
                  reason=RefundReason.CUSTOMER.value, status=REFUND_PROCESSED, refunded_at=t))
    booking.status = BookingStatus.CANCELLED.value
    booking.cancelled_at = t
    changes = _free_seats(booking)
    db.commit()

    manager.push_seat_changes(show.id, changes)
    email_service.dispatch(background_tasks, email_service.send_booking_cancelled, ctx, str(refund_amount))
    notify_waitlist(db, show, background_tasks)
    return {"booking_number": booking.booking_number, "status": booking.status,
            "refund_amount": refund_amount, "refund_percentage": int(pct * 100),
            "message": f"Booking cancelled. Refund of Rs. {refund_amount} will be credited."}


# ---------------------------------------------------------------------------- organizer show cancellation
def cancel_show(db: Session, show: Show, background_tasks) -> dict:
    if show.status != ShowStatus.SCHEDULED.value:
        raise HTTPException(status_code=400, detail=f"Show is already {show.status}")
    t = now()
    show.status = ShowStatus.CANCELLED.value

    bookings = db.query(Booking).filter(Booking.show_id == show.id).with_for_update().all()
    notices = []
    refunded_total = Decimal("0.00")
    for b in bookings:
        if b.status == BookingStatus.CONFIRMED.value:
            ctx = booking_context(b)
            payment = _mark_payment_refunded(b)
            amount = money(b.grand_total)            # 100% incl. convenience fee and GST
            db.add(Refund(booking_id=b.id, payment_id=payment.id if payment else None, amount=amount,
                          reason=RefundReason.SHOW.value, status=REFUND_PROCESSED, refunded_at=t))
            b.status = BookingStatus.CANCELLED.value
            b.cancelled_at = t
            for bs in b.seats:
                bs.confirmed_seat_id = None
            notices.append((b.customer_id, ctx, str(amount)))
            refunded_total += amount
        elif b.status == BookingStatus.PENDING.value:
            b.status = BookingStatus.CANCELLED.value
            b.cancelled_at = t

    for w in db.query(Waitlist).filter(Waitlist.show_id == show.id,
                                       Waitlist.status == WaitlistStatus.WAITING.value).all():
        w.status = WaitlistStatus.CLOSED.value
    db.commit()

    seat_service.clear_show_locks(show.id)
    cache_service.clear_event_cache()

    # live notifications: everyone watching the seat map + each affected customer
    manager.push_show_event(show.id, {"type": "show_cancelled", "show_id": show.id,
                                      "message": "This show has been cancelled by the organizer."})
    for customer_id, ctx, amount in notices:
        manager.push_user_notification(customer_id, {
            "type": "show_cancelled", "show_id": show.id, "booking_number": ctx["booking_number"],
            "refund_amount": amount,
            "message": f"{ctx['event_title']} on {ctx['show_datetime']} was cancelled. Full refund of Rs. {amount} issued."})
        email_service.dispatch(background_tasks, email_service.send_show_cancelled, ctx, amount)

    return {"show_id": show.id, "status": show.status, "bookings_cancelled": len(notices),
            "total_refunded": refunded_total}


# ---------------------------------------------------------------------------- waitlist
def notify_waitlist(db: Session, show: Show, background_tasks) -> int:
    """Email waitlisted customers, in the order they joined, when enough seats are free."""
    if show.status != ShowStatus.SCHEDULED.value or now() >= show.booking_closes_at:
        return 0
    total_available, by_cat = seat_service.available_counts(db, show)
    if total_available == 0:
        return 0
    entries = (db.query(Waitlist).filter(Waitlist.show_id == show.id, Waitlist.status == WaitlistStatus.WAITING.value)
               .order_by(Waitlist.created_at, Waitlist.id).all())
    notified = 0
    show_dt = show.start_at.strftime("%d %b %Y, %I:%M %p")
    for w in entries:
        pool = by_cat.get(w.category, 0) if w.category else total_available
        if pool < w.seats_requested:
            continue
        # reserve the seats on paper for this customer so later entries only get what is left
        if w.category:
            by_cat[w.category] -= w.seats_requested
        total_available -= w.seats_requested
        w.status = WaitlistStatus.NOTIFIED.value
        w.notified_at = now()
        email_service.dispatch(background_tasks, email_service.send_waitlist_available, w.customer.email,
                               w.customer.name, show.event.title, show_dt, w.seats_requested, w.category)
        manager.push_user_notification(w.customer_id, {
            "type": "waitlist_seats_available", "show_id": show.id,
            "message": f"Seats are now available for {show.event.title} ({show_dt})."})
        notified += 1
        if total_available <= 0:
            break
    db.commit()
    return notified
