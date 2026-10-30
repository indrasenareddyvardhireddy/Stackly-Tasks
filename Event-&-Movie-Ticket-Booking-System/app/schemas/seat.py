from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Money


class SeatMapItem(BaseModel):
    seat_id: int
    row_label: str
    seat_number: int
    label: str
    category: str
    price: Money
    status: str                       # Available | Locked | Booked | Unavailable
    locked_by_you: bool = False


class SeatMapResponse(BaseModel):
    show_id: int
    show_status: str
    total_seats: int
    available_seats: int
    seats: List[SeatMapItem]


class LockRequest(BaseModel):
    seat_ids: List[int] = Field(min_length=1, max_length=10)


class ReleaseRequest(BaseModel):
    seat_ids: Optional[List[int]] = Field(default=None, description="Omit to release all your locks for this show")


class LockedSeat(BaseModel):
    seat_id: int
    label: str
    category: str
    price: Money


class LockResponse(BaseModel):
    show_id: int
    seats: List[LockedSeat]
    expires_at: datetime
    expires_in_seconds: int
    message: str


class ReleaseResponse(BaseModel):
    released: List[str]
    not_locked: List[str]
    message: str


class SeatSuggestion(BaseModel):
    seat_ids: List[int]
    labels: List[str]
    category: str
    total_price: Money
