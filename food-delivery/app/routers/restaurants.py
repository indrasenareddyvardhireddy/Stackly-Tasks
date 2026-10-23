from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.security import OWNER, get_current_user, require_roles
from app.database import get_db
from app.models import Coupon, MenuCategory, MenuItem, Restaurant, User
from app.schemas.schemas import (AvailabilityIn, CategoryIn, MenuItemIn, MenuItemUpdate, OpenStatusIn,
                                 RestaurantIn, RestaurantUpdate)
from app.services.restaurant_service import (get_owned_restaurant, get_restaurant_or_404, restaurant_dict,
                                             restaurant_is_open)
from app.utils.common import row_dict
from app.utils.geo import haversine_km, travel_minutes
from app.utils.timeutil import now

router = APIRouter(tags=["Restaurants & Menu"])


# NOTE: /restaurants/nearby and /restaurants/me are declared before /restaurants/{restaurant_id}
@router.get("/restaurants/nearby")
def nearby(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180),
           name: Optional[str] = None, cuisine_type: Optional[str] = None, veg_only: bool = False,
           min_rating: Optional[float] = Query(None, ge=0, le=5), has_offers: bool = False,
           sort_by: Literal["distance", "rating", "estimated_delivery_minutes"] = "distance",
           order: Literal["asc", "desc"] = "asc", skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
           db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Restaurant).filter(Restaurant.is_active.is_(True), Restaurant.is_temporarily_closed.is_(False))
    if name:
        q = q.filter(Restaurant.name.ilike(f"%{name}%"))
    if cuisine_type:
        q = q.filter(Restaurant.cuisine_type.ilike(f"%{cuisine_type}%"))
    if min_rating is not None:
        q = q.filter(Restaurant.average_rating >= min_rating)
    if veg_only:
        veg_ids = {r[0] for r in db.query(MenuItem.restaurant_id).filter(
            MenuItem.is_veg.is_(True), MenuItem.is_available.is_(True), MenuItem.is_deleted.is_(False)).distinct()}
        q = q.filter(Restaurant.id.in_(veg_ids or {0}))
    if has_offers:
        t = now()
        coupons = db.query(Coupon.restaurant_id).filter(
            Coupon.is_active.is_(True), Coupon.valid_from <= t, Coupon.valid_to >= t).all()
        if any(c[0] is None for c in coupons):  # a platform-wide coupon applies everywhere
            pass
        else:
            q = q.filter(Restaurant.id.in_({c[0] for c in coupons} or {0}))
    results = []
    for r in q.all():
        if not restaurant_is_open(r):
            continue
        dist = haversine_km(latitude, longitude, r.latitude, r.longitude)
        if dist > r.delivery_radius_km:
            continue
        results.append(restaurant_dict(
            r, distance_km=round(dist, 2),
            estimated_delivery_minutes=round(r.avg_preparation_minutes + travel_minutes(dist))))
    key = {"distance": "distance_km", "rating": "average_rating",
           "estimated_delivery_minutes": "estimated_delivery_minutes"}[sort_by]
    results.sort(key=lambda x: x[key], reverse=(order == "desc"))
    return {"total": len(results), "skip": skip, "limit": limit, "items": results[skip: skip + limit]}


@router.post("/restaurants", status_code=201)
def create_restaurant(data: RestaurantIn, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(OWNER, approved=True))):
    r = Restaurant(owner_id=user.id, **data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return restaurant_dict(r)


@router.get("/restaurants/me")
def my_restaurants(db: Session = Depends(get_db), user: User = Depends(require_roles(OWNER))):
    return [restaurant_dict(r) for r in db.query(Restaurant).filter(Restaurant.owner_id == user.id)]


@router.get("/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return restaurant_dict(get_restaurant_or_404(db, restaurant_id))


@router.put("/restaurants/{restaurant_id}")
def update_restaurant(restaurant_id: int, data: RestaurantUpdate, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(OWNER, approved=True))):
    r = get_owned_restaurant(db, restaurant_id, user)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(r, k, v)
    if r.opening_time >= r.closing_time:
        raise HTTPException(422, "opening_time must be before closing_time")
    db.commit()
    db.refresh(r)
    return restaurant_dict(r)


@router.put("/restaurants/{restaurant_id}/open-status")
def set_open_status(restaurant_id: int, data: OpenStatusIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(OWNER, approved=True))):
    r = get_owned_restaurant(db, restaurant_id, user)
    r.is_temporarily_closed = data.is_temporarily_closed
    db.commit()
    return restaurant_dict(r)


@router.post("/restaurants/{restaurant_id}/categories", status_code=201)
def create_category(restaurant_id: int, data: CategoryIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(OWNER, approved=True))):
    get_owned_restaurant(db, restaurant_id, user)
    c = MenuCategory(restaurant_id=restaurant_id, name=data.name)
    db.add(c)
    db.commit()
    return row_dict(c)


@router.post("/restaurants/{restaurant_id}/menu-items", status_code=201)
def create_menu_item(restaurant_id: int, data: MenuItemIn, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(OWNER, approved=True))):
    get_owned_restaurant(db, restaurant_id, user)
    cat = db.get(MenuCategory, data.category_id)
    if not cat or cat.restaurant_id != restaurant_id:
        raise HTTPException(404, "Category not found in this restaurant")
    item = MenuItem(restaurant_id=restaurant_id, **data.model_dump())
    db.add(item)
    db.commit()
    return row_dict(item)


@router.get("/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    r = get_restaurant_or_404(db, restaurant_id)
    out = []
    for cat in db.query(MenuCategory).filter(MenuCategory.restaurant_id == restaurant_id).order_by(MenuCategory.id):
        items = db.query(MenuItem).filter(MenuItem.category_id == cat.id, MenuItem.is_deleted.is_(False)).all()
        out.append({"category_id": cat.id, "category": cat.name,
                    "items": [{**row_dict(i), "unavailable": not i.is_available} for i in items]})
    return {"restaurant": restaurant_dict(r), "menu": out}


def _owned_item(db: Session, item_id: int, user: User) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Menu item not found")
    get_owned_restaurant(db, item.restaurant_id, user)
    return item


@router.put("/menu-items/{item_id}")
def update_menu_item(item_id: int, data: MenuItemUpdate, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(OWNER, approved=True))):
    item = _owned_item(db, item_id, user)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        cat = db.get(MenuCategory, changes["category_id"])
        if not cat or cat.restaurant_id != item.restaurant_id:
            raise HTTPException(404, "Category not found in this restaurant")
    for k, v in changes.items():
        setattr(item, k, v)
    db.commit()
    return row_dict(item)


@router.put("/menu-items/{item_id}/availability")
def set_availability(item_id: int, data: AvailabilityIn, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(OWNER, approved=True))):
    item = _owned_item(db, item_id, user)
    item.is_available = data.is_available
    db.commit()
    return row_dict(item)


@router.delete("/menu-items/{item_id}")
def delete_menu_item(item_id: int, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(OWNER, approved=True))):
    item = _owned_item(db, item_id, user)
    item.is_deleted = True  # soft delete: old orders keep their snapshot
    item.is_available = False
    db.commit()
    return {"message": "Menu item deleted"}
