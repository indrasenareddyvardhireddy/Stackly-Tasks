from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.config import settings
from app.database import get_db
from app.models.enums import Role, SeatCategory
from app.models.user import User
from app.schemas.seat import (LockRequest, LockResponse, ReleaseRequest, ReleaseResponse, SeatMapItem,
                              SeatMapResponse, SeatSuggestion)
from app.services import seat_service
from app.services.rate_limit import check_rate_limit
from app.services.show_access import get_visible_show
from app.websockets.manager import manager

router = APIRouter(tags=["Seat Locking"])

# Customers, Organizers and Admins can lock / release seats
lock_roles = require_roles(Role.CUSTOMER, Role.ORGANIZER, Role.ADMIN)


def _check_can_lock(show, user: User):
    """Organizers may hold seats only for their own events (Admin: any show, Customer: any visible show)."""
    if user.role == Role.ORGANIZER.value and show.event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="You can lock seats only for your own events")


@router.get("/shows/{show_id}/seats", response_model=SeatMapResponse)
def get_seat_map(show_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Live seat map. Never cached - it changes every second."""
    show = get_visible_show(db, show_id, user)
    states = seat_service.get_seat_states(db, show)
    items = [SeatMapItem(seat_id=s["seat_id"], row_label=s["row_label"], seat_number=s["seat_number"],
                         label=s["label"], category=s["category"], price=s["price"], status=s["status"],
                         locked_by_you=(s["status"] == "Locked" and s["locked_by"] == user.id)) for s in states]
    return SeatMapResponse(show_id=show.id, show_status=show.status, total_seats=len(items),
                           available_seats=sum(1 for i in items if i.status == "Available"), seats=items)


@router.post("/shows/{show_id}/lock-seats", response_model=LockResponse)
def lock_seats(show_id: int, payload: LockRequest, db: Session = Depends(get_db),
               user: User = Depends(lock_roles)):
    check_rate_limit(f"rl:lock:{user.id}", settings.LOCK_RATE_LIMIT_PER_MINUTE)
    show = get_visible_show(db, show_id, user)
    _check_can_lock(show, user)
    result = seat_service.lock_seats(db, show, user.id, payload.seat_ids)
    manager.push_seat_changes(show.id, result.pop("changes"))
    return result


@router.delete("/shows/{show_id}/lock-seats", response_model=ReleaseResponse)
def release_seats(show_id: int, payload: Optional[ReleaseRequest] = Body(default=None),
                  db: Session = Depends(get_db), user: User = Depends(lock_roles)):
    """Releases only the caller's own locks. Omit the body to release all of them for this show."""
    show = get_visible_show(db, show_id, user)
    _check_can_lock(show, user)
    seat_ids = payload.seat_ids if payload else None
    result = seat_service.release_locks(db, show, user.id, seat_ids)
    manager.push_seat_changes(show.id, result.pop("changes"))
    return result


@router.get("/shows/{show_id}/seats/suggest", response_model=List[SeatSuggestion])
def suggest_seats(show_id: int, count: int = Query(..., ge=1, le=10), category: Optional[SeatCategory] = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Bonus: best available adjacent seats for the given count (and category)."""
    show = get_visible_show(db, show_id, user)
    return seat_service.suggest_best_seats(db, show, count, category.value if category else None)
