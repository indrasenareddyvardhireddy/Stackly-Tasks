"""Seat map, Redis seat locking, single-gap rule and best-seat suggestion."""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.booking import BookedSeat, Booking
from app.models.enums import BookingStatus, ShowStatus
from app.models.event import SeatCategoryPrice, Show
from app.models.venue import Seat
from app.redis_client import redis_client as r
from app.utils.billing import money
from app.utils.helpers import row_sort_key, seat_label
from app.utils.seat_rules import find_single_gap_violations
from app.utils.time import now

logger = logging.getLogger(__name__)

# delete a lock only if it still belongs to the caller (atomic compare-and-delete)
_RELEASE_SCRIPT = r.register_script(
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
)

DYNAMIC_PRICING_THRESHOLD = Decimal("0.80")
DYNAMIC_PRICING_MULTIPLIER = Decimal("1.10")


# ----------------------------------------------------------------------------- redis helpers
def lock_key(show_id: int, seat_id: int) -> str:
    return f"lock:show:{show_id}:seat:{seat_id}"


def release_lock_if_owner(show_id: int, seat_id: int, user_id: int) -> bool:
    return bool(_RELEASE_SCRIPT(keys=[lock_key(show_id, seat_id)], args=[str(user_id)]))


def get_lock_owners(show_id: int, seat_ids: List[int]) -> Dict[int, int]:
    """{seat_id: customer_id} for every seat that currently has a lock."""
    if not seat_ids:
        return {}
    values = r.mget([lock_key(show_id, sid) for sid in seat_ids])
    return {sid: int(v) for sid, v in zip(seat_ids, values) if v is not None}


def clear_show_locks(show_id: int):
    for key in r.scan_iter(match=f"lock:show:{show_id}:seat:*", count=500):
        r.delete(key)


# ----------------------------------------------------------------------------- db helpers
def ordered_seats(db: Session, screen_id: int) -> List[Seat]:
    seats = db.query(Seat).filter(Seat.screen_id == screen_id).all()
    return sorted(seats, key=lambda s: (row_sort_key(s.row_label), s.seat_number))


def get_booked_seat_ids(db: Session, show_id: int) -> Set[int]:
    rows = (db.query(BookedSeat.seat_id)
            .filter(BookedSeat.show_id == show_id, BookedSeat.confirmed_seat_id.isnot(None)).all())
    return {row[0] for row in rows}


def get_base_prices(db: Session, show_id: int) -> Dict[str, Decimal]:
    rows = db.query(SeatCategoryPrice).filter(SeatCategoryPrice.show_id == show_id).all()
    return {row.category: Decimal(row.price) for row in rows}


def price_multiplier(booked_count: int, active_total: int) -> Decimal:
    """Dynamic pricing (bonus): +10% when more than 80% of the active seats are booked."""
    if active_total and Decimal(booked_count) / Decimal(active_total) > DYNAMIC_PRICING_THRESHOLD:
        return DYNAMIC_PRICING_MULTIPLIER
    return Decimal("1.00")


def current_multiplier(db: Session, show: Show) -> Decimal:
    seats = db.query(Seat).filter(Seat.screen_id == show.screen_id, Seat.is_active.is_(True)).count()
    booked = get_booked_seat_ids(db, show.id)
    return price_multiplier(len(booked), seats)


def get_seat_states(db: Session, show: Show) -> List[dict]:
    """The live seat map: Available / Locked / Booked / Unavailable for every seat of the show."""
    seats = ordered_seats(db, show.screen_id)
    booked = get_booked_seat_ids(db, show.id)
    owners = get_lock_owners(show.id, [s.id for s in seats])
    base_prices = get_base_prices(db, show.id)
    active_total = sum(1 for s in seats if s.is_active)
    multiplier = price_multiplier(len(booked), active_total)
    show_open = show.status == ShowStatus.SCHEDULED.value

    states = []
    for s in seats:
        locked_by = None
        if s.id in booked:
            status = "Booked"
        elif not s.is_active or not show_open:
            status = "Unavailable"
        elif s.id in owners:
            status, locked_by = "Locked", owners[s.id]
        else:
            status = "Available"
        price = money(base_prices.get(s.category, Decimal("0")) * multiplier)
        states.append({
            "seat_id": s.id, "row_label": s.row_label, "seat_number": s.seat_number,
            "label": seat_label(s.row_label, s.seat_number), "category": s.category,
            "price": price, "status": status, "locked_by": locked_by,
        })
    return states


def apply_viewer(states: List[dict], user_id: int) -> List[dict]:
    """Mark the viewer's own locks as 'Yours' (used for the WebSocket seat map)."""
    out = []
    for s in states:
        item = {k: v for k, v in s.items() if k != "locked_by"}
        if s["status"] == "Locked" and s["locked_by"] == user_id:
            item["status"] = "Yours"
        out.append(item)
    return out


def change(seat: Seat, status: str, locked_by: Optional[int] = None) -> dict:
    return {"seat_id": seat.id, "label": seat_label(seat.row_label, seat.seat_number),
            "status": status, "locked_by": locked_by}


def available_counts(db: Session, show: Show):
    """(total_available, {category: available}) - used for waitlist rules."""
    by_cat: Dict[str, int] = defaultdict(int)
    for s in get_seat_states(db, show):
        if s["status"] == "Available":
            by_cat[s["category"]] += 1
    return sum(by_cat.values()), dict(by_cat)


# ----------------------------------------------------------------------------- rules
def ensure_show_open(show: Show):
    if show.status != ShowStatus.SCHEDULED.value:
        raise HTTPException(status_code=400, detail=f"Show is {show.status}; seats cannot be locked or booked")
    if now() >= show.booking_closes_at:
        raise HTTPException(status_code=400, detail="Booking for this show is closed")


def lock_seats(db: Session, show: Show, user_id: int, seat_ids: List[int]) -> dict:
    """All-or-nothing seat lock. Returns the payload for LockResponse plus the websocket changes."""
    ensure_show_open(show)
    seat_ids = list(dict.fromkeys(seat_ids))
    all_seats = ordered_seats(db, show.screen_id)
    seat_map = {s.id: s for s in all_seats}

    missing = [sid for sid in seat_ids if sid not in seat_map]
    if missing:
        raise HTTPException(status_code=404, detail=f"Seats {missing} do not belong to this show's screen")

    booked = get_booked_seat_ids(db, show.id)
    owners = get_lock_owners(show.id, list(seat_map.keys()))

    # 1) availability pre-check
    unavailable = []
    for sid in seat_ids:
        seat = seat_map[sid]
        if not seat.is_active:
            unavailable.append({"seat_id": sid, "label": seat.label, "reason": "Unavailable"})
        elif sid in booked:
            unavailable.append({"seat_id": sid, "label": seat.label, "reason": "Booked"})
        elif sid in owners and owners[sid] != user_id:
            unavailable.append({"seat_id": sid, "label": seat.label, "reason": "Locked"})
    if unavailable:
        raise HTTPException(status_code=409, detail={
            "message": "Some seats are not available", "unavailable_seats": unavailable})

    # 2) max 10 seats per show (already booked + currently locked + new)
    my_locks = {sid for sid, uid in owners.items() if uid == user_id}
    my_booked = (db.query(func.count(BookedSeat.id)).join(Booking, Booking.id == BookedSeat.booking_id)
                 .filter(Booking.customer_id == user_id, BookedSeat.show_id == show.id,
                         BookedSeat.confirmed_seat_id.isnot(None)).scalar() or 0)
    total = len(my_locks | set(seat_ids)) + my_booked
    if total > settings.MAX_SEATS_PER_SHOW:
        raise HTTPException(status_code=400, detail=(
            f"You can lock or book at most {settings.MAX_SEATS_PER_SHOW} seats per show "
            f"(you already hold {len(my_locks) + my_booked})"))

    # 3) no single empty seat between the customer's seats and another taken seat
    selected = my_locks | set(seat_ids)
    taken = {s.id for s in all_seats
             if (not s.is_active) or s.id in booked or (s.id in owners and owners[s.id] != user_id)}
    rows: Dict[str, List[Seat]] = defaultdict(list)
    for s in all_seats:
        rows[s.row_label].append(s)
    orphans: List[str] = []
    for row in {seat_map[sid].row_label for sid in seat_ids}:
        ids = [s.id for s in rows[row]]
        orphans += [seat_map[i].label for i in find_single_gap_violations(ids, selected, taken)]
    if orphans:
        raise HTTPException(status_code=400, detail=(
            f"This selection would leave a single empty seat ({', '.join(sorted(orphans))}) between your "
            "seats and another taken seat. Please choose different seats."))

    # 4) atomic acquisition: SET NX EX per seat, roll everything back if any seat is lost
    acquired: List[int] = []
    already_mine: List[int] = []
    failed: List[int] = []
    for sid in seat_ids:
        key = lock_key(show.id, sid)
        if r.set(key, str(user_id), nx=True, ex=settings.LOCK_TTL_SECONDS):
            acquired.append(sid)
        elif r.get(key) == str(user_id):
            already_mine.append(sid)
        else:
            failed.append(sid)
    if failed:
        for sid in acquired:
            release_lock_if_owner(show.id, sid, user_id)
        raise HTTPException(status_code=409, detail={
            "message": "Some seats were just taken by someone else; none of your seats were locked",
            "unavailable_seats": [{"seat_id": sid, "label": seat_map[sid].label, "reason": "Locked"}
                                  for sid in failed]})

    ttls = [r.ttl(lock_key(show.id, sid)) for sid in seat_ids]
    ttl = min([t for t in ttls if t and t > 0] or [settings.LOCK_TTL_SECONDS])
    prices = get_base_prices(db, show.id)
    mult = price_multiplier(len(booked), sum(1 for s in all_seats if s.is_active))
    return {
        "show_id": show.id,
        "seats": [{"seat_id": sid, "label": seat_map[sid].label, "category": seat_map[sid].category,
                   "price": money(prices.get(seat_map[sid].category, Decimal("0")) * mult)} for sid in seat_ids],
        "expires_at": now() + timedelta(seconds=ttl),
        "expires_in_seconds": ttl,
        "message": f"Seats locked. Complete the booking and payment within {ttl // 60} min {ttl % 60} sec.",
        "changes": [change(seat_map[sid], "Locked", user_id) for sid in acquired],
    }


def release_locks(db: Session, show: Show, user_id: int, seat_ids: Optional[List[int]]) -> dict:
    all_seats = ordered_seats(db, show.screen_id)
    seat_map = {s.id: s for s in all_seats}
    owners = get_lock_owners(show.id, list(seat_map.keys()))

    if seat_ids is None:
        target = [sid for sid, uid in owners.items() if uid == user_id]
        not_locked: List[int] = []
    else:
        target, not_locked = [], []
        for sid in dict.fromkeys(seat_ids):
            if sid not in seat_map:
                raise HTTPException(status_code=404, detail=f"Seat {sid} does not belong to this show's screen")
            if sid not in owners:
                not_locked.append(sid)
            elif owners[sid] != user_id:
                raise HTTPException(status_code=403, detail=f"Seat {seat_map[sid].label} is locked by another customer")
            else:
                target.append(sid)

    if target:   # locked seats that already belong to a pending booking must be released by cancelling it
        in_booking = (db.query(BookedSeat.seat_id).join(Booking, Booking.id == BookedSeat.booking_id)
                      .filter(Booking.customer_id == user_id, Booking.show_id == show.id,
                              Booking.status == BookingStatus.PENDING.value,
                              BookedSeat.seat_id.in_(target)).all())
        if in_booking:
            labels = [seat_map[row[0]].label for row in in_booking]
            raise HTTPException(status_code=409, detail=(
                f"Seats {', '.join(labels)} belong to a pending booking. Cancel the booking instead."))

    changes = []
    for sid in target:
        if release_lock_if_owner(show.id, sid, user_id):
            changes.append(change(seat_map[sid], "Available"))
    return {
        "released": [seat_map[sid].label for sid in target],
        "not_locked": [seat_map[sid].label for sid in not_locked],
        "message": f"{len(changes)} seat(s) released",
        "changes": changes,
    }


def suggest_best_seats(db: Session, show: Show, count: int, category: Optional[str], limit: int = 3) -> List[dict]:
    """Bonus: best adjacent seats - rows near the middle, seats near the centre of the row."""
    states = get_seat_states(db, show)
    rows: Dict[str, List[dict]] = defaultdict(list)
    for s in states:
        rows[s["row_label"]].append(s)
    ordered_rows = sorted(rows.items(), key=lambda kv: row_sort_key(kv[0]))
    mid_row = (len(ordered_rows) - 1) / 2
    candidates = []
    for ri, (_, seats) in enumerate(ordered_rows):
        seats.sort(key=lambda s: s["seat_number"])
        ids = [s["seat_id"] for s in seats]
        taken = {s["seat_id"] for s in seats if s["status"] != "Available"}
        centre = (len(seats) - 1) / 2
        for start in range(0, len(seats) - count + 1):
            window = seats[start:start + count]
            if any(w["status"] != "Available" for w in window):
                continue
            if category and any(w["category"] != category for w in window):
                continue
            if window[-1]["seat_number"] - window[0]["seat_number"] != count - 1:
                continue
            if find_single_gap_violations(ids, {w["seat_id"] for w in window}, taken):
                continue
            score = abs(ri - mid_row) * 1.5 + abs((start + (count - 1) / 2) - centre)
            candidates.append((score, window))
    candidates.sort(key=lambda c: c[0])
    return [{"seat_ids": [w["seat_id"] for w in win], "labels": [w["label"] for w in win],
             "category": win[0]["category"], "total_price": sum((w["price"] for w in win), Decimal("0"))}
            for _, win in candidates[:limit]]
