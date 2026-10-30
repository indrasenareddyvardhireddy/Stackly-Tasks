"""
Payments: the mock gateway AND Razorpay share the same confirm / late-payment-refund logic.

Entry points
  pay_booking()             mock payment          (POST /bookings/{id}/pay)
  create_razorpay_order()   Razorpay order        (POST /bookings/{id}/razorpay-order)
  razorpay_verify()         Checkout callback     (POST /bookings/{id}/razorpay-verify)
  handle_razorpay_event()   webhook               (POST /webhooks/razorpay)
"""
import logging
import secrets
import string
from decimal import Decimal
from typing import List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.booking import BookedSeat, Booking, Payment, Refund, Ticket
from app.models.enums import (REFUND_PROCESSED, BookingStatus, PaymentMethod, PaymentStatus,
                              RefundReason, ShowStatus, SimulateStatus)
from app.models.user import User
from app.redis_client import redis_client as r
from app.services import email_service, razorpay_service, seat_service
from app.services.booking_service import booking_context
from app.services.ticket_service import generate_ticket_pdf, make_qr_value, pdf_full_path
from app.utils.helpers import random_code
from app.utils.time import now
from app.websockets.manager import manager

logger = logging.getLogger(__name__)
RAZORPAY_METHOD = "Razorpay"


def to_paise(amount) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


def _transaction_id(db: Session) -> str:
    day = now().strftime("%Y%m%d")
    while True:
        txn = f"TXN-{day}-{random_code(6)}"
        if not db.query(Payment.id).filter(Payment.transaction_id == txn).first():
            return txn


def _lock_booking(db: Session, booking_id: int):
    """Row lock so simultaneous payments / webhooks for one booking are processed one at a time."""
    return db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()


def _check_payable(booking: Booking):
    if booking.status == BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=409, detail="This booking is already confirmed and paid")
    if booking.status in (BookingStatus.EXPIRED.value, BookingStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail=f"Payment is not possible: booking is {booking.status}")
    if booking.show.status != ShowStatus.SCHEDULED.value:
        raise HTTPException(status_code=400, detail="Payment is not possible: the show is not open")


def _result(payment: Payment, booking: Booking, message: str) -> dict:
    confirmed = booking.status == BookingStatus.CONFIRMED.value
    return {"payment": payment, "booking_status": booking.status, "message": message,
            "ticket_url": f"/bookings/{booking.id}/ticket" if confirmed else None}


def _seats_conflict(db: Session, booking: Booking, user_id: int) -> tuple:
    """
    Make sure every seat of the booking can still be given to this customer.
    Returns (conflict, newly_acquired_seat_ids). Locks that expired are re-acquired when the seat is
    still free; if somebody else locked / booked the seat meanwhile it is a conflict.
    """
    show_id = booking.show_id
    seat_ids = [bs.seat_id for bs in booking.seats]
    taken_elsewhere = (db.query(BookedSeat.seat_id)
                       .filter(BookedSeat.show_id == show_id, BookedSeat.confirmed_seat_id.isnot(None),
                               BookedSeat.seat_id.in_(seat_ids), BookedSeat.booking_id != booking.id).first())
    if taken_elsewhere:
        return True, []
    acquired: List[int] = []
    for sid in seat_ids:
        key = seat_service.lock_key(show_id, sid)
        owner = r.get(key)
        if owner == str(user_id):
            continue
        if owner is None and r.set(key, str(user_id), nx=True, ex=60):
            acquired.append(sid)
            continue
        for a in acquired:
            seat_service.release_lock_if_owner(show_id, a, user_id)
        return True, []
    return False, acquired


# ----------------------------------------------------------------------------- building blocks
def _record_failed(db: Session, booking: Booking, method: str, background_tasks, **extra) -> dict:
    """Failed payment: saved as Failed, booking stays Pending Payment so the customer can retry."""
    ctx = booking_context(booking)
    payment = Payment(booking_id=booking.id, transaction_id=_transaction_id(db), amount=booking.grand_total,
                      payment_method=method, status=PaymentStatus.FAILED.value, paid_at=None, **extra)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    email_service.dispatch(background_tasks, email_service.send_payment_failed, ctx)
    return _result(payment, booking, "Payment failed. You can retry until your seat lock expires.")


def _late_payment_refund(db: Session, booking_id: int, customer: User, method: str, background_tasks,
                         touch_booking: bool = True, reason: str = None, **extra) -> dict:
    """
    Money was received but the seats cannot be given: refund automatically (payment -> Refunded,
    Late Payment refund row). `touch_booking=False` is used when the booking is already
    Confirmed / Cancelled / Expired and must stay as it is.
    """
    booking = _lock_booking(db, booking_id)
    t = now()
    payment = Payment(booking_id=booking.id, transaction_id=_transaction_id(db), amount=booking.grand_total,
                      payment_method=method, status=PaymentStatus.REFUNDED.value, paid_at=t, **extra)
    db.add(payment)
    db.flush()
    db.add(Refund(booking_id=booking.id, payment_id=payment.id, amount=booking.grand_total,
                  reason=RefundReason.LATE.value, status=REFUND_PROCESSED, refunded_at=t))
    if touch_booking:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = t
    db.commit()
    db.refresh(payment)
    ctx = booking_context(booking)
    email_service.dispatch(background_tasks, email_service.send_late_payment_refund, ctx, reason)
    manager.push_user_notification(customer.id, {
        "type": "payment_refunded", "booking_number": booking.booking_number,
        "message": reason or "Your seats were taken before payment completed. The amount has been refunded."})
    return _result(payment, booking, (reason or
                   "Payment received after your seat lock expired and the seats were taken by someone else. "
                   "The amount was refunded automatically and the booking is cancelled."))


def _confirm_payment(db: Session, booking: Booking, customer: User, method: str, background_tasks, **extra) -> dict:
    """Successful payment on a payable booking (caller holds the booking row lock)."""
    booking_id, show_id = booking.id, booking.show_id
    ctx = booking_context(booking)

    conflict, acquired = _seats_conflict(db, booking, customer.id)
    if conflict:
        return _late_payment_refund(db, booking_id, customer, method, background_tasks, **extra)

    try:
        t = now()
        payment = Payment(booking_id=booking.id, transaction_id=_transaction_id(db), amount=booking.grand_total,
                          payment_method=method, status=PaymentStatus.SUCCESS.value, paid_at=t, **extra)
        db.add(payment)
        for bs in booking.seats:                      # permanent seats (unique per show)
            bs.confirmed_seat_id = bs.seat_id
        booking.status = BookingStatus.CONFIRMED.value
        booking.confirmed_at = t
        ticket = Ticket(booking_id=booking.id, qr_value=make_qr_value(booking.booking_number))
        db.add(ticket)
        db.flush()                                    # unique constraints are checked here
        ticket.pdf_path = generate_ticket_pdf(ctx, ticket.qr_value)
        db.commit()                                   # ONE transaction for everything above
    except IntegrityError:
        db.rollback()
        for sid in acquired:
            seat_service.release_lock_if_owner(show_id, sid, customer.id)
        return _late_payment_refund(db, booking_id, customer, method, background_tasks, **extra)
    except Exception:
        db.rollback()
        for sid in acquired:
            seat_service.release_lock_if_owner(show_id, sid, customer.id)
        logger.exception("Payment processing failed")
        raise HTTPException(status_code=500, detail="Could not complete the payment, please retry")

    db.refresh(payment)
    # after commit: release the locks, push the live seat map, email the ticket
    changes = []
    for bs in booking.seats:
        seat_service.release_lock_if_owner(booking.show_id, bs.seat_id, customer.id)
        changes.append(seat_service.change(bs.seat, "Booked"))
    manager.push_seat_changes(booking.show_id, changes)
    email_service.dispatch(background_tasks, email_service.send_booking_confirmed, ctx,
                           pdf_full_path(booking.ticket.pdf_path))
    return _result(payment, booking, "Payment successful. Your booking is confirmed.")


# ----------------------------------------------------------------------------- mock payment
def _mock_gateway_ids(existing_order_id: str = None) -> dict:
    """Fake ids in Razorpay's format (order_ / pay_ + 14 chars). Only used by the MOCK payment.
    A booking keeps ONE order id (like a real Razorpay order); every attempt gets a new payment id."""
    alphabet = string.ascii_letters + string.digits
    rand = lambda: "".join(secrets.choice(alphabet) for _ in range(14))
    return {"razorpay_order_id": existing_order_id or "order_" + rand(), "razorpay_payment_id": "pay_" + rand()}


def pay_booking(db: Session, booking_id: int, user: User, method: PaymentMethod,
                simulate: SimulateStatus, background_tasks) -> dict:
    booking = _lock_booking(db, booking_id)
    if not booking or booking.customer_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    _check_payable(booking)       # the amount is always the booking's grand_total, never from the request
    ids = _mock_gateway_ids(booking.razorpay_order_id)   # simulated Razorpay-style ids
    booking.razorpay_order_id = ids["razorpay_order_id"]  # saved on the booking too (committed with the payment)
    if simulate == SimulateStatus.FAILED:
        return _record_failed(db, booking, method.value, background_tasks, **ids)
    return _confirm_payment(db, booking, user, method.value, background_tasks, **ids)


# ----------------------------------------------------------------------------- Razorpay
def create_razorpay_order(db: Session, booking_id: int, customer: User) -> dict:
    booking = _lock_booking(db, booking_id)
    if not booking or booking.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    _check_payable(booking)
    if not booking.razorpay_order_id:          # retries of the same booking reuse the same order
        order = razorpay_service.create_order(
            to_paise(booking.grand_total), booking.booking_number,
            {"booking_id": str(booking.id), "booking_number": booking.booking_number})
        booking.razorpay_order_id = order["id"]
        db.commit()
        db.refresh(booking)
    return {"order_id": booking.razorpay_order_id, "amount": to_paise(booking.grand_total), "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID, "booking_number": booking.booking_number,
            "expires_at": booking.expires_at}


def _process_captured(db: Session, booking: Booking, order_id: str, payment_id: str, signature, background_tasks) -> dict:
    """A verified, captured Razorpay payment. Idempotent: the same payment id is processed only once."""
    extra = {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature}
    existing = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
    if existing:
        return _result(existing, booking, "This payment was already processed")

    customer = booking.customer
    if booking.status != BookingStatus.PENDING.value or booking.show.status != ShowStatus.SCHEDULED.value:
        # money arrived for a booking that can no longer be fulfilled -> refund, leave the booking untouched
        return _late_payment_refund(
            db, booking.id, customer, RAZORPAY_METHOD, background_tasks, touch_booking=False,
            reason=f"Your payment could not be applied because the booking is {booking.status}.", **extra)
    return _confirm_payment(db, booking, customer, RAZORPAY_METHOD, background_tasks, **extra)


def razorpay_verify(db: Session, booking_id: int, customer: User, order_id: str, payment_id: str,
                    signature: str, background_tasks) -> dict:
    booking = _lock_booking(db, booking_id)
    if not booking or booking.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not booking.razorpay_order_id or booking.razorpay_order_id != order_id:
        raise HTTPException(status_code=400, detail="This Razorpay order does not belong to the booking")
    # a wrong signature must NEVER confirm a booking
    if not razorpay_service.verify_payment_signature(order_id, payment_id, signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    return _process_captured(db, booking, order_id, payment_id, signature, background_tasks)


def handle_razorpay_event(db: Session, event: dict, background_tasks=None) -> str:
    """Webhook events payment.captured / payment.failed. Always returns a short status string."""
    name = event.get("event")
    try:
        entity = event["payload"]["payment"]["entity"]
        order_id, payment_id = entity["order_id"], entity["id"]
    except (KeyError, TypeError):
        return "ignored: unexpected payload"
    if name not in ("payment.captured", "payment.failed"):
        return f"ignored: {name}"

    booking = (db.query(Booking).filter(Booking.razorpay_order_id == order_id).with_for_update().first())
    if not booking:
        return "ignored: unknown order"
    if db.query(Payment.id).filter(Payment.razorpay_payment_id == payment_id).first():
        return "already processed"

    if name == "payment.captured":
        if entity.get("amount") != to_paise(booking.grand_total):
            logger.error("Razorpay amount mismatch for %s: got %s expected %s", booking.booking_number,
                         entity.get("amount"), to_paise(booking.grand_total))
            return "ignored: amount mismatch"
        _process_captured(db, booking, order_id, payment_id, None, background_tasks)
        return "payment captured processed"

    if booking.status == BookingStatus.PENDING.value:            # payment.failed
        _record_failed(db, booking, RAZORPAY_METHOD, background_tasks,
                       razorpay_order_id=order_id, razorpay_payment_id=payment_id)
        return "payment failure recorded"
    db.rollback()
    return "ignored: booking not pending"