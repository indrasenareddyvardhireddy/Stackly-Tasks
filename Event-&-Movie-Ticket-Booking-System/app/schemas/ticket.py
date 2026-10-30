from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    qr_value: str = Field(min_length=5, description="The value encoded in the QR code")


class ScanResponse(BaseModel):
    message: str
    booking_number: str
    customer_name: str
    seats: List[str]
    seat_count: int
    event_title: str
    screen_name: str
    show_start: datetime
    scanned_at: datetime


class EntriesResponse(BaseModel):
    show_id: int
    total_bookings: int
    entered_bookings: int
    total_tickets: int
    entered_tickets: int
    pending_entry_bookings: int
