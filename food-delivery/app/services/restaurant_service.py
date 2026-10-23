from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Restaurant
from app.utils.common import row_dict
from app.utils.timeutil import now


def restaurant_is_open(r: Restaurant, at=None) -> bool:
    t = (at or now()).time()
    return bool(r.is_active and not r.is_temporarily_closed and r.opening_time <= t <= r.closing_time)


def restaurant_dict(r: Restaurant, **extra) -> dict:
    d = row_dict(r)
    d["is_open"] = restaurant_is_open(r)
    d.update(extra)
    return d


def get_restaurant_or_404(db: Session, restaurant_id: int) -> Restaurant:
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(404, "Restaurant not found")
    return r


def get_owned_restaurant(db: Session, restaurant_id: int, user) -> Restaurant:
    r = get_restaurant_or_404(db, restaurant_id)
    if r.owner_id != user.id:
        raise HTTPException(403, "You can manage only your own restaurants")
    return r
