from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import SeatCategory
from app.schemas.common import Money, ORMModel


class RefundOut(ORMModel):
    id: int
    booking_id: int
    payment_id: Optional[int] = None
    amount: Money
    reason: str
    status: str
    refunded_at: datetime


class CancelResponse(BaseModel):
    booking_number: str
    status: str
    refund_amount: Money
    refund_percentage: int
    message: str


class WaitlistCreate(BaseModel):
    seats_requested: int = Field(ge=1, le=10)
    category: Optional[SeatCategory] = None


class WaitlistOut(ORMModel):
    id: int
    show_id: int
    customer_id: int
    customer_name: Optional[str] = None
    seats_requested: int
    category: Optional[str] = None
    status: str
    notified_at: Optional[datetime] = None
    created_at: datetime
