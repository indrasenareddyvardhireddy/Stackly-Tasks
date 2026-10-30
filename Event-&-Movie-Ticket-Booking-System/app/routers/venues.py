from collections import OrderedDict
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.booking import BookedSeat
from app.models.enums import Role
from app.models.event import Show
from app.models.user import User
from app.models.venue import Screen, Seat, Venue
from app.schemas.common import Page
from app.schemas.venue import (LayoutRow, ScreenCreate, ScreenLayout, ScreenOut, SeatBulkCreate, SeatOut,
                               SeatStatusUpdate, VenueCreate, VenueOut, VenueUpdate)
from app.services import seat_service
from app.services.venue_service import create_seats_bulk
from app.utils.helpers import row_sort_key
from app.utils.pagination import Pagination, paginate_response
from app.utils.time import now
from app.websockets.manager import manager

router = APIRouter(tags=["Venues, Screens & Seats"])
admin_only = require_roles(Role.ADMIN)


@router.post("/venues", response_model=VenueOut, status_code=201)
def create_venue(payload: VenueCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/venues", response_model=Page[VenueOut])
def list_venues(city: Optional[str] = None, is_active: Optional[bool] = None,
                page: Pagination = Depends(), db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    q = db.query(Venue)
    if city:
        q = q.filter(func.lower(Venue.city) == city.lower())
    if is_active is not None:
        q = q.filter(Venue.is_active.is_(is_active))
    total = q.count()
    items = q.order_by(Venue.id).offset(page.skip).limit(page.limit).all()
    return paginate_response(items, total, page)


@router.put("/venues/{venue_id}", response_model=VenueOut)
def update_venue(venue_id: int, payload: VenueUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    db.commit()
    db.refresh(venue)
    return venue


@router.post("/venues/{venue_id}/screens", response_model=ScreenOut, status_code=201)
def create_screen(venue_id: int, payload: ScreenCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    screen = Screen(venue_id=venue.id, name=payload.name, total_seats=payload.total_seats)
    db.add(screen)
    db.commit()
    db.refresh(screen)
    return screen


@router.post("/screens/{screen_id}/seats/bulk", response_model=List[SeatOut], status_code=201)
def bulk_create_seats(screen_id: int, payload: SeatBulkCreate, db: Session = Depends(get_db),
                      _: User = Depends(admin_only)):
    screen = db.get(Screen, screen_id)
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")
    return create_seats_bulk(db, screen, payload.row_start, payload.row_end,
                             payload.seats_per_row, payload.category.value)


@router.get("/screens/{screen_id}/layout", response_model=ScreenLayout)
def screen_layout(screen_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    screen = db.get(Screen, screen_id)
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")
    seats = seat_service.ordered_seats(db, screen_id)
    grouped: "OrderedDict[str, list]" = OrderedDict()
    for s in sorted(seats, key=lambda s: (row_sort_key(s.row_label), s.seat_number)):
        grouped.setdefault(s.row_label, []).append(s)
    return ScreenLayout(
        screen_id=screen.id, screen_name=screen.name, venue_id=screen.venue_id, total_seats=len(seats),
        rows=[LayoutRow(row_label=row, seats=[SeatOut.model_validate(s) for s in row_seats])
              for row, row_seats in grouped.items()])


@router.put("/seats/{seat_id}/status", response_model=SeatOut)
def update_seat_status(seat_id: int, payload: SeatStatusUpdate, db: Session = Depends(get_db),
                       _: User = Depends(admin_only)):
    seat = db.get(Seat, seat_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    if not payload.is_active:
        future_booking = (db.query(BookedSeat.id).join(Show, Show.id == BookedSeat.show_id)
                          .filter(BookedSeat.seat_id == seat.id, BookedSeat.confirmed_seat_id.isnot(None),
                                  Show.start_at > now()).first())
        if future_booking:
            raise HTTPException(status_code=409, detail="Seat has confirmed bookings for upcoming shows")
    seat.is_active = payload.is_active
    db.commit()
    db.refresh(seat)
    # push the new state to everybody watching upcoming shows on this screen
    upcoming = db.query(Show.id).filter(Show.screen_id == seat.screen_id, Show.start_at > now()).all()
    for (show_id,) in upcoming:
        manager.push_seat_changes(show_id, [seat_service.change(seat, "Available" if seat.is_active else "Unavailable")])
    return seat
