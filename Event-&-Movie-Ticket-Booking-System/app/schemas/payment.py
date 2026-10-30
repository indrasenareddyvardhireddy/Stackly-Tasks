from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import PaymentMethod, SimulateStatus
from app.schemas.common import Money, ORMModel


class PaymentRequest(BaseModel):
    payment_method: PaymentMethod
    simulate_status: SimulateStatus = SimulateStatus.SUCCESS   # only to test both outcomes


class PaymentOut(ORMModel):
    id: int
    booking_id: int
    transaction_id: str
    amount: Money
    payment_method: str
    status: str
    paid_at: Optional[datetime] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    created_at: datetime


class PaymentResponse(BaseModel):
    payment: PaymentOut
    booking_status: str
    message: str
    ticket_url: Optional[str] = None


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int                 # in paise (Rs.1 = 100 paise)
    currency: str = "INR"
    key_id: str
    booking_number: str
    expires_at: Optional[datetime] = None


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
