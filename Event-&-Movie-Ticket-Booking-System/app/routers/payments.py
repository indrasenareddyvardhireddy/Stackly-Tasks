from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.enums import Role
from app.models.user import User
from app.routers.bookings import get_booking_for_user
from app.schemas.payment import (PaymentOut, PaymentRequest, PaymentResponse, RazorpayOrderResponse,
                                 RazorpayVerifyRequest)
from app.services import payment_service

router = APIRouter(tags=["Payments"])



@router.get("/bookings/{booking_id}/payments", response_model=List[PaymentOut])
def booking_payments(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = get_booking_for_user(db, booking_id, user)
    return booking.payments


@router.post("/bookings/{booking_id}/razorpay-order", response_model=RazorpayOrderResponse)
def razorpay_order(booking_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.CUSTOMER))):
    """Creates a Razorpay order (amount in paise, booking number as receipt). Open Razorpay Checkout with the result."""
    return payment_service.create_razorpay_order(db, booking_id, user)


@router.post("/bookings/{booking_id}/razorpay-verify", response_model=PaymentResponse)
def razorpay_verify(booking_id: int, payload: RazorpayVerifyRequest, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db), user: User = Depends(require_roles(Role.CUSTOMER))):
    """Called with the three values Razorpay Checkout returns. A wrong signature never confirms a booking."""
    return payment_service.razorpay_verify(db, booking_id, user, payload.razorpay_order_id,
                                           payload.razorpay_payment_id, payload.razorpay_signature,
                                           background_tasks)