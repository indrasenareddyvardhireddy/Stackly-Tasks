from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AgeRating, EventCategory, SeatCategory
from app.schemas.common import Money, ORMModel


class EventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: EventCategory
    language: str = Field(min_length=2, max_length=50)
    description: Optional[str] = None
    duration_minutes: int = Field(ge=30, le=300, description="Between 30 and 300 minutes")
    age_rating: AgeRating
    status: str = Field(default="Draft", pattern="^(Draft|Published)$")


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    category: Optional[EventCategory] = None
    language: Optional[str] = Field(default=None, min_length=2, max_length=50)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=30, le=300)
    age_rating: Optional[AgeRating] = None
    status: Optional[str] = Field(default=None, pattern="^(Draft|Published|Cancelled)$")


class PriceIn(BaseModel):
    category: SeatCategory
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PriceOut(ORMModel):
    category: str
    price: Money


class ShowCreate(BaseModel):
    screen_id: int
    show_date: date
    start_time: time
    prices: List[PriceIn] = Field(min_length=1)

    @field_validator("show_date")
    @classmethod
    def date_not_past(cls, v: date):
        if v < date.today():
            raise ValueError("Show date must be in the future")
        return v

    @field_validator("start_time")
    @classmethod
    def drop_timezone(cls, v):
        # the app works in naive server-local time; ignore any "+05:30" / "Z" suffix
        return v.replace(tzinfo=None) if v is not None else v


class ShowUpdate(BaseModel):
    screen_id: Optional[int] = None
    show_date: Optional[date] = None
    start_time: Optional[time] = None
    prices: Optional[List[PriceIn]] = Field(default=None, min_length=1)

    @field_validator("start_time")
    @classmethod
    def drop_timezone(cls, v):
        # the app works in naive server-local time; ignore any "+05:30" / "Z" suffix
        return v.replace(tzinfo=None) if v is not None else v

    @field_validator("show_date")
    @classmethod
    def date_not_past(cls, v: Optional[date]):
        if v is not None and v < date.today():
            raise ValueError("Show date must be in the future")
        return v


class ShowOut(ORMModel):
    id: int
    event_id: int
    screen_id: int
    screen_name: str
    venue_id: int
    venue_name: str
    city: str
    show_date: date
    start_time: time
    end_time: time
    start_at: datetime
    end_at: datetime
    booking_closes_at: datetime
    status: str
    prices: List[PriceOut]


class EventOut(ORMModel):
    id: int
    organizer_id: int
    title: str
    category: str
    language: str
    description: Optional[str] = None
    duration_minutes: int
    age_rating: str
    status: str
    created_at: datetime
    updated_at: datetime
    next_show_at: Optional[datetime] = None
    min_price: Optional[Money] = None


class EventDetail(EventOut):
    shows: List[ShowOut] = []
