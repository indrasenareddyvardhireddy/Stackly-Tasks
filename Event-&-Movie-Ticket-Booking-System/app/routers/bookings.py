from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.booking import Booking
from app.models.enums import BookingStatus, Role
from app.models.event import Event, Show
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut
from app.schemas.common import Page
from app.services import booking_service
from app.services.show_access import get_visible_show
from app.utils.pagination import Pagination, paginate_response

router = APIRouter(tags=["Bookings"])


def get_booking_for_user(db: Session, booking_id: int, user: User) -> Booking:
    """Customers: own bookings. Organizers: bookings of their own events. Admin: everything."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user.role == Role.ADMIN.value:
        return booking
    if user.role == Role.CUSTOMER.value and booking.customer_id == user.id:
        return booking
    if user.role == Role.ORGANIZER.value and booking.show.event.organizer_id == user.id:
        return booking
    raise HTTPException(status_code=403, detail="You do not have access to this booking")


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(Role.CUSTOMER))):
    show = get_visible_show(db, payload.show_id, user)
    return booking_service.create_booking(db, show, user, payload.seat_ids)


@router.get("/bookings", response_model=Page[BookingOut])
def list_bookings(status: Optional[BookingStatus] = None, show_id: Optional[int] = None,
                  from_date: Optional[date] = None, to_date: Optional[date] = None,
                  page: Pagination = Depends(), db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.CUSTOMER, Role.ORGANIZER, Role.ADMIN))):
    q = db.query(Booking)
    if user.role == Role.CUSTOMER.value:
        q = q.filter(Booking.customer_id == user.id)
    elif user.role == Role.ORGANIZER.value:
        q = (q.join(Show, Show.id == Booking.show_id).join(Event, Event.id == Show.event_id)
             .filter(Event.organizer_id == user.id))
    if status:
        q = q.filter(Booking.status == status.value)
    if show_id:
        q = q.filter(Booking.show_id == show_id)
    if from_date:
        q = q.filter(Booking.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.filter(Booking.created_at <= datetime.combine(to_date, time.max))
    total = q.count()
    items = q.order_by(Booking.id.desc()).offset(page.skip).limit(page.limit).all()
    return paginate_response(items, total, page)


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_booking_for_user(db, booking_id, user)
