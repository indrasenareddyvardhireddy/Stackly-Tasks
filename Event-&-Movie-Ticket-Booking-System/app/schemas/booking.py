from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import BookingStatus
from app.schemas.common import Money, ORMModel


class BookingCreate(BaseModel):
    show_id: int
    seat_ids: List[int] = Field(min_length=1, max_length=10)


class BookedSeatOut(ORMModel):
    seat_id: int
    label: str
    row_label: str
    seat_number: int
    category: str
    price: Money


class BookingOut(ORMModel):
    id: int
    booking_number: str
    customer_id: int
    show_id: int
    event_title: str
    venue_name: str
    screen_name: str
    show_start: datetime
    seat_count: int
    ticket_total: Money
    convenience_fee: Money
    gst_amount: Money
    grand_total: Money
    status: str
    expires_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    seats: List[BookedSeatOut]


class BookingFilter(BaseModel):
    status: Optional[BookingStatus] = None
    show_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
