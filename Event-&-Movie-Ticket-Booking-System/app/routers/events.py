from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_approved_organizer, get_current_user, get_optional_user, require_roles
from app.config import settings
from app.database import get_db
from app.models.booking import Booking
from app.models.enums import (BookingStatus, EventCategory, EventSortBy, EventStatus, Role, ShowStatus, SortOrder)
from app.models.event import Event, SeatCategoryPrice, Show
from app.models.user import User
from app.models.venue import Screen, Seat, Venue
from app.schemas.common import Page
from app.schemas.event import (EventCreate, EventDetail, EventOut, EventUpdate, PriceIn, ShowCreate, ShowOut,
                               ShowUpdate)
from app.services import cache_service
from app.services.cancellation_service import cancel_show
from app.utils.pagination import Pagination, paginate_response
from app.utils.time import now

router = APIRouter(tags=["Events & Shows"])


# ------------------------------------------------------------------------------ helpers
def _scope(user: Optional[User]) -> str:
    if user and user.role == Role.ADMIN.value:
        return "admin"
    if user and user.role == Role.ORGANIZER.value:
        return f"org{user.id}"
    return "public"


def _can_see_event(event: Event, user: Optional[User]) -> bool:
    if event.status == EventStatus.PUBLISHED.value:
        return True
    if user and user.role == Role.ADMIN.value:
        return True
    return bool(user and user.role == Role.ORGANIZER.value and event.organizer_id == user.id)


def _own_event(db: Session, event_id: int, user: User) -> Event:
    event = db.get(Event, event_id)
    if not event or event.organizer_id != user.id:
        raise HTTPException(status_code=404, detail="Event not found")   # organizers manage only their own
    return event


def _show_times(show_date: date, start_time, duration_minutes: int):
    start_at = datetime.combine(show_date, start_time.replace(tzinfo=None))
    end_at = start_at + timedelta(minutes=duration_minutes)
    closes = start_at - timedelta(minutes=settings.BOOKING_CLOSE_MINUTES)
    return start_at, end_at, closes


def _check_overlap(db: Session, screen_id: int, start_at: datetime, end_at: datetime, exclude_id: Optional[int] = None):
    gap = timedelta(minutes=settings.CLEANING_GAP_MINUTES)
    q = db.query(Show).filter(Show.screen_id == screen_id, Show.status != ShowStatus.CANCELLED.value,
                              Show.start_at < end_at + gap, Show.end_at > start_at - gap)
    if exclude_id:
        q = q.filter(Show.id != exclude_id)
    clash = q.first()
    if clash:
        raise HTTPException(status_code=409, detail=(
            f"Overlaps with show #{clash.id} on this screen "
            f"({clash.start_at:%d %b %H:%M} - {clash.end_at:%H:%M}); a {settings.CLEANING_GAP_MINUTES}-minute "
            "cleaning gap is required between shows"))


def _validate_prices(db: Session, screen_id: int, prices: List[PriceIn]):
    screen_categories = {c for (c,) in db.query(Seat.category).filter(
        Seat.screen_id == screen_id, Seat.is_active.is_(True)).distinct().all()}
    if not screen_categories:
        raise HTTPException(status_code=400, detail="The screen has no active seats")
    given = [p.category.value for p in prices]
    if len(set(given)) != len(given):
        raise HTTPException(status_code=400, detail="Duplicate seat category in prices")
    missing = screen_categories - set(given)
    if missing:
        raise HTTPException(status_code=400, detail=f"Price required for every seat category: missing {sorted(missing)}")
    extra = set(given) - screen_categories
    if extra:
        raise HTTPException(status_code=400, detail=f"The screen has no {sorted(extra)} seats")


def _replace_prices(db: Session, show: Show, prices: List[PriceIn]):
    """Delete-then-insert (a plain collection replace would INSERT before DELETE and hit the unique key)."""
    db.query(SeatCategoryPrice).filter(SeatCategoryPrice.show_id == show.id).delete(synchronize_session=False)
    db.expire(show, ["prices"])
    for p in prices:
        db.add(SeatCategoryPrice(show_id=show.id, category=p.category.value, price=p.price))


def _confirmed_booking_exists(db: Session, show_id: int) -> bool:
    return db.query(Booking.id).filter(Booking.show_id == show_id,
                                       Booking.status == BookingStatus.CONFIRMED.value).first() is not None


# ------------------------------------------------------------------------------ events
@router.post("/events", response_model=EventOut, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db), user: User = Depends(get_approved_organizer)):
    event = Event(organizer_id=user.id, title=payload.title, category=payload.category.value,
                  language=payload.language, description=payload.description,
                  duration_minutes=payload.duration_minutes, age_rating=payload.age_rating.value,
                  status=payload.status)
    db.add(event)
    db.commit()
    db.refresh(event)
    cache_service.clear_event_cache()
    return event


@router.get("/events", response_model=Page[EventOut])
def list_events(
    title: Optional[str] = Query(None, description="Partial match"),
    city: Optional[str] = None,
    category: Optional[EventCategory] = None,
    language: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    min_price: Optional[Decimal] = Query(None, ge=0),
    max_price: Optional[Decimal] = Query(None, ge=0),
    sort_by: EventSortBy = EventSortBy.SHOW_DATE,
    order: SortOrder = SortOrder.ASC,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    scope = _scope(user)
    params = {"title": title, "city": city, "category": category.value if category else None,
              "language": language, "from_date": from_date, "to_date": to_date, "min_price": min_price,
              "max_price": max_price, "sort_by": sort_by.value, "order": order.value,
              "skip": page.skip, "limit": page.limit}
    key = cache_service.make_key("list", scope, params)
    cached = cache_service.cache_get(key)
    if cached is not None:
        return cached

    q = db.query(Event)
    if scope == "public":
        q = q.filter(Event.status == EventStatus.PUBLISHED.value)      # customers: Published only
    elif scope.startswith("org"):
        q = q.filter(Event.organizer_id == user.id)
    if title:
        q = q.filter(Event.title.ilike(f"%{title}%"))
    if category:
        q = q.filter(Event.category == category.value)
    if language:
        q = q.filter(func.lower(Event.language) == language.lower())

    # per-event show aggregates (next show + cheapest price) honouring the show-level filters
    sq = (db.query(Show.event_id.label("event_id"), func.min(Show.start_at).label("next_show"),
                   func.min(SeatCategoryPrice.price).label("min_price"))
          .join(Screen, Screen.id == Show.screen_id).join(Venue, Venue.id == Screen.venue_id)
          .join(SeatCategoryPrice, SeatCategoryPrice.show_id == Show.id)
          .filter(Show.status == ShowStatus.SCHEDULED.value))
    if city:
        sq = sq.filter(func.lower(Venue.city) == city.lower())
    if from_date:
        sq = sq.filter(Show.show_date >= from_date)
    if to_date:
        sq = sq.filter(Show.show_date <= to_date)
    if min_price is not None:
        sq = sq.filter(SeatCategoryPrice.price >= min_price)
    if max_price is not None:
        sq = sq.filter(SeatCategoryPrice.price <= max_price)
    sq = sq.group_by(Show.event_id).subquery()

    show_filtered = any(v is not None for v in (city, from_date, to_date, min_price, max_price))
    q = q.join(sq, sq.c.event_id == Event.id) if show_filtered else q.outerjoin(sq, sq.c.event_id == Event.id)
    total = q.count()

    if sort_by == EventSortBy.TITLE:
        order_cols = [Event.title.asc() if order == SortOrder.ASC else Event.title.desc()]
    else:
        col = sq.c.next_show if sort_by == EventSortBy.SHOW_DATE else sq.c.min_price
        order_cols = [col.is_(None), col.asc() if order == SortOrder.ASC else col.desc()]   # events without shows last
    rows = (q.add_columns(sq.c.next_show, sq.c.min_price).order_by(*order_cols, Event.id)
            .offset(page.skip).limit(page.limit).all())

    items = []
    for event, next_show, cheapest in rows:
        out = EventOut.model_validate(event)
        out.next_show_at = next_show
        out.min_price = cheapest
        items.append(out)
    result = paginate_response(items, total, page)
    cache_service.cache_set(key, result)
    return result


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: int, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    key = cache_service.make_key("detail", _scope(user), {"id": event_id})
    cached = cache_service.cache_get(key)
    if cached is not None:
        return cached
    event = db.get(Event, event_id)
    if not event or not _can_see_event(event, user):
        raise HTTPException(status_code=404, detail="Event not found")
    shows = (db.query(Show).filter(Show.event_id == event.id, Show.status == ShowStatus.SCHEDULED.value)
             .order_by(Show.start_at).all())
    detail = EventDetail.model_validate(event)
    detail.shows = [ShowOut.model_validate(s) for s in shows]
    prices = [p.price for s in shows for p in s.prices]
    detail.next_show_at = shows[0].start_at if shows else None
    detail.min_price = min(prices) if prices else None
    cache_service.cache_set(key, detail)
    return detail


@router.put("/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventUpdate, background_tasks: BackgroundTasks,
                 db: Session = Depends(get_db), user: User = Depends(get_approved_organizer)):
    event = _own_event(db, event_id, user)
    if event.status in (EventStatus.CANCELLED.value, EventStatus.COMPLETED.value):
        raise HTTPException(status_code=400, detail=f"A {event.status} event cannot be edited")
    data = payload.model_dump(exclude_unset=True)
    for field in ("category", "age_rating"):
        if field in data and data[field] is not None:
            data[field] = data[field].value
    cancelling = data.get("status") == EventStatus.CANCELLED.value
    for field, value in data.items():
        if value is None and field != "description":
            continue
        setattr(event, field, value)
    db.commit()
    if cancelling:      # cancelling an event cancels (and refunds) all its upcoming shows
        for show in db.query(Show).filter(Show.event_id == event.id, Show.status == ShowStatus.SCHEDULED.value).all():
            cancel_show(db, show, background_tasks)
    db.refresh(event)
    cache_service.clear_event_cache()
    return event


# ------------------------------------------------------------------------------ shows
@router.post("/events/{event_id}/shows", response_model=ShowOut, status_code=201)
def create_show(event_id: int, payload: ShowCreate, db: Session = Depends(get_db),
                user: User = Depends(get_approved_organizer)):
    event = _own_event(db, event_id, user)
    if event.status in (EventStatus.CANCELLED.value, EventStatus.COMPLETED.value):
        raise HTTPException(status_code=400, detail=f"Cannot add shows to a {event.status} event")
    screen = db.get(Screen, payload.screen_id)
    if not screen or not screen.venue.is_active:
        raise HTTPException(status_code=404, detail="Screen not found or its venue is inactive")

    start_at, end_at, closes = _show_times(payload.show_date, payload.start_time, event.duration_minutes)
    if start_at <= now():
        raise HTTPException(status_code=400, detail="Show must start in the future")
    _validate_prices(db, screen.id, payload.prices)
    _check_overlap(db, screen.id, start_at, end_at)

    show = Show(event_id=event.id, screen_id=screen.id, show_date=payload.show_date, start_time=payload.start_time,
                end_time=end_at.time(), start_at=start_at, end_at=end_at, booking_closes_at=closes,
                status=ShowStatus.SCHEDULED.value)
    show.prices = [SeatCategoryPrice(category=p.category.value, price=p.price) for p in payload.prices]
    db.add(show)
    db.commit()
    db.refresh(show)
    cache_service.clear_event_cache()
    return show


@router.get("/events/{event_id}/shows", response_model=List[ShowOut])
def list_shows(event_id: int, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    event = db.get(Event, event_id)
    if not event or not _can_see_event(event, user):
        raise HTTPException(status_code=404, detail="Event not found")
    return db.query(Show).filter(Show.event_id == event.id).order_by(Show.start_at).all()


@router.put("/shows/{show_id}", response_model=ShowOut)
def update_show(show_id: int, payload: ShowUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_approved_organizer)):
    show = db.get(Show, show_id)
    if not show or show.event.organizer_id != user.id:
        raise HTTPException(status_code=404, detail="Show not found")
    if show.status != ShowStatus.SCHEDULED.value:
        raise HTTPException(status_code=400, detail=f"A {show.status} show cannot be edited")

    data = payload.model_dump(exclude_unset=True)
    changes_schedule = any(k in data and data[k] is not None for k in ("screen_id", "show_date", "start_time"))
    if (changes_schedule or payload.prices) and _confirmed_booking_exists(db, show.id):
        raise HTTPException(status_code=409, detail=(
            "Prices and schedule cannot be changed after the first confirmed booking"))

    screen_id = payload.screen_id or show.screen_id
    if payload.screen_id:
        screen = db.get(Screen, payload.screen_id)
        if not screen or not screen.venue.is_active:
            raise HTTPException(status_code=404, detail="Screen not found or its venue is inactive")
    show_date = payload.show_date or show.show_date
    start_time = payload.start_time or show.start_time
    start_at, end_at, closes = _show_times(show_date, start_time, show.event.duration_minutes)
    if changes_schedule:
        if start_at <= now():
            raise HTTPException(status_code=400, detail="Show must start in the future")
        _check_overlap(db, screen_id, start_at, end_at, exclude_id=show.id)
        show.screen_id, show.show_date, show.start_time = screen_id, show_date, start_time
        show.start_at, show.end_at, show.end_time, show.booking_closes_at = start_at, end_at, end_at.time(), closes

    if payload.prices:
        _validate_prices(db, screen_id, payload.prices)
        _replace_prices(db, show, payload.prices)
    db.commit()
    db.refresh(show)
    cache_service.clear_event_cache()
    return show


@router.put("/shows/{show_id}/cancel")
def cancel_show_endpoint(show_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
                         user: User = Depends(require_roles(Role.ORGANIZER, Role.ADMIN))):
    show = db.get(Show, show_id)
    if not show or (user.role == Role.ORGANIZER.value and show.event.organizer_id != user.id):
        raise HTTPException(status_code=404, detail="Show not found")
    return cancel_show(db, show, background_tasks)
