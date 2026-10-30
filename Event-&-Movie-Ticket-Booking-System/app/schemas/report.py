from datetime import date
from typing import List

from pydantic import BaseModel

from app.schemas.common import Money


class AdminDashboard(BaseModel):
    date: date
    todays_bookings: int
    todays_revenue: Money
    todays_refund_count: int
    todays_refunds: Money
    active_events: int
    tickets_scanned_today: int


class ShowSales(BaseModel):
    show_id: int
    show_start: str
    venue_name: str
    tickets_sold: int
    revenue: Money
    refunds: Money


class EventSales(BaseModel):
    event_id: int
    title: str
    tickets_sold: int
    revenue: Money
    refunds: Money
    shows: List[ShowSales]


class CategoryOccupancy(BaseModel):
    category: str
    total_seats: int
    booked_seats: int
    occupancy_percent: float


class ShowOccupancy(BaseModel):
    show_id: int
    event_title: str
    show_start: str
    total_seats: int
    booked_seats: int
    occupancy_percent: float
    categories: List[CategoryOccupancy]


class TopEvent(BaseModel):
    event_id: int
    title: str
    tickets_sold: int
    revenue: Money


class RefundSummaryRow(BaseModel):
    reason: str
    count: int
    amount: Money


class RefundReport(BaseModel):
    total_count: int
    total_amount: Money
    by_reason: List[RefundSummaryRow]
