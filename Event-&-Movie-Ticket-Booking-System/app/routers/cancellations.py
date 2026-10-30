from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.booking import Booking
from app.models.enums import BookingStatus, Role, ShowStatus, WaitlistStatus
from app.models.event import Show
from app.models.user import User
from app.models.waitlist import Waitlist
from app.routers.bookings import get_booking_for_user
from app.schemas.cancellation import CancelResponse, RefundOut, WaitlistCreate, WaitlistOut
from app.schemas.common import MessageResponse, Page
from app.services import cancellation_service, seat_service
from app.services.show_access import get_visible_show
from app.utils.pagination import Pagination, paginate_response
from app.utils.time import now

router = APIRouter(tags=["Cancellations, Refunds & Waitlist"])


@router.put("/bookings/{booking_id}/cancel", response_model=CancelResponse)
def cancel_booking(booking_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(Role.CUSTOMER))):
    return cancellation_service.cancel_booking(db, booking_id, user, background_tasks)


@router.get("/bookings/{booking_id}/refunds", response_model=List[RefundOut])
def booking_refunds(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_booking_for_user(db, booking_id, user).refunds


# ------------------------------------------------------------------------------ waitlist
@router.post("/shows/{show_id}/waitlist", response_model=WaitlistOut, status_code=201)
def join_waitlist(show_id: int, payload: WaitlistCreate, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.CUSTOMER))):
    show = get_visible_show(db, show_id, user)
    if show.status != ShowStatus.SCHEDULED.value or now() >= show.booking_closes_at:
        raise HTTPException(status_code=400, detail="Booking is closed for this show")

    # only for sold-out shows (sold out = no Available seat in the preferred category, or in the whole show)
    total_available, by_cat = seat_service.available_counts(db, show)
    category = payload.category.value if payload.category else None
    available = by_cat.get(category, 0) if category else total_available
    if available > 0:
        raise HTTPException(status_code=409, detail=(
            f"Seats are still available{' in ' + category if category else ''}; the waitlist is only for sold-out shows"))

    if db.query(Waitlist.id).filter(Waitlist.show_id == show.id, Waitlist.customer_id == user.id).first():
        raise HTTPException(status_code=409, detail="You are already on the waitlist for this show")
    if db.query(Booking.id).filter(Booking.show_id == show.id, Booking.customer_id == user.id,
                                   Booking.status.in_([BookingStatus.CONFIRMED.value,
                                                       BookingStatus.PENDING.value])).first():
        raise HTTPException(status_code=409, detail="You already have a booking for this show")

    entry = Waitlist(show_id=show.id, customer_id=user.id, seats_requested=payload.seats_requested,
                     category=category, status=WaitlistStatus.WAITING.value)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You are already on the waitlist for this show")
    db.refresh(entry)
    return entry


@router.get("/shows/{show_id}/waitlist", response_model=Page[WaitlistOut])
def list_waitlist(show_id: int, page: Pagination = Depends(), db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.ADMIN, Role.ORGANIZER, Role.CUSTOMER))):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    q = db.query(Waitlist).filter(Waitlist.show_id == show_id)
    if user.role == Role.ORGANIZER.value:
        if show.event.organizer_id != user.id:
            raise HTTPException(status_code=403, detail="This is not your event")
    elif user.role == Role.CUSTOMER.value:
        q = q.filter(Waitlist.customer_id == user.id)       # customers only see their own entry
    total = q.count()
    items = q.order_by(Waitlist.created_at, Waitlist.id).offset(page.skip).limit(page.limit).all()
    return paginate_response(items, total, page)


@router.delete("/waitlist/{waitlist_id}", response_model=MessageResponse)
def leave_waitlist(waitlist_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN))):
    entry = db.get(Waitlist, waitlist_id)
    if not entry or (user.role == Role.CUSTOMER.value and entry.customer_id != user.id):
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Removed from the waitlist"}
