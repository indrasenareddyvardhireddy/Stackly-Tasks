from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SeatCategory
from app.schemas.common import ORMModel


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=2, max_length=255)
    is_active: bool = True


class VenueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    address: Optional[str] = Field(default=None, min_length=2, max_length=255)
    is_active: Optional[bool] = None


class VenueOut(ORMModel):
    id: int
    name: str
    city: str
    address: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScreenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Screen 1"])
    total_seats: int = Field(default=0, ge=0)


class ScreenOut(ORMModel):
    id: int
    venue_id: int
    name: str
    total_seats: int
    created_at: datetime


class SeatBulkCreate(BaseModel):
    """Example: rows A..E as Silver with 12 seats each."""
    row_start: str = Field(pattern=r"^[A-Z]$", examples=["A"])
    row_end: str = Field(pattern=r"^[A-Z]$", examples=["E"])
    seats_per_row: int = Field(ge=1, le=100, examples=[12])
    category: SeatCategory

    @model_validator(mode="after")
    def check_rows(self):
        if self.row_end < self.row_start:
            raise ValueError("row_end must be the same as or after row_start")
        return self


class SeatOut(ORMModel):
    id: int
    screen_id: int
    row_label: str
    seat_number: int
    category: str
    is_active: bool
    label: str


class SeatStatusUpdate(BaseModel):
    is_active: bool


class LayoutRow(BaseModel):
    row_label: str
    seats: List[SeatOut]


class ScreenLayout(BaseModel):
    screen_id: int
    screen_name: str
    venue_id: int
    total_seats: int
    rows: List[LayoutRow]
