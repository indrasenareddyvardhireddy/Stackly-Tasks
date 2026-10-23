from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, CUSTOMER, OWNER, require_roles
from app.database import get_db
from app.models import Coupon, Restaurant, User
from app.schemas.schemas import CouponIn, CouponUpdate
from app.services.cart_service import cart_totals, get_or_create_cart
from app.services.coupon_service import validate_coupon
from app.utils.common import row_dict
from app.utils.timeutil import now

router = APIRouter(prefix="/coupons", tags=["Coupons"])
staff = require_roles(ADMIN, OWNER, approved=True)


def _check_manage(db: Session, coupon: Coupon, user: User):
    if user.role == ADMIN:
        return
    if coupon.created_by != user.id:
        raise HTTPException(403, "You can manage only your own restaurant coupons")


@router.post("", status_code=201)
def create_coupon(data: CouponIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    if user.role == OWNER:
        r = db.get(Restaurant, data.restaurant_id) if data.restaurant_id else None
        if not r or r.owner_id != user.id:
            raise HTTPException(403, "Restaurant owners can create coupons only for their own restaurants")
    elif data.restaurant_id and not db.get(Restaurant, data.restaurant_id):
        raise HTTPException(404, "Restaurant not found")
    code = data.code.upper()
    if db.query(Coupon).filter(func.upper(Coupon.code) == code).first():
        raise HTTPException(409, "Coupon code already exists")
    c = Coupon(**{**data.model_dump(), "code": code}, created_by=user.id)  # admin + no restaurant = platform-wide
    db.add(c)
    db.commit()
    return row_dict(c)


@router.get("/available")
def available_coupons(db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    """Coupons usable right now for the restaurant in the cart, with the discount they'd give."""
    cart = get_or_create_cart(db, user)
    if not cart.items:
        return []
    item_total, _ = cart_totals(cart)
    t = now()
    q = db.query(Coupon).filter(Coupon.is_active.is_(True), Coupon.valid_from <= t, Coupon.valid_to >= t,
                                (Coupon.restaurant_id.is_(None)) | (Coupon.restaurant_id == cart.restaurant_id))
    out = []
    for c in q:
        try:
            discount = validate_coupon(db, c, user.id, cart.restaurant_id, item_total)
        except HTTPException:
            continue
        out.append({**row_dict(c), "discount_you_get": discount})
    return out


@router.get("")
def list_coupons(restaurant_id: Optional[int] = None, is_active: Optional[bool] = None,
                 discount_type: Optional[Literal["Percentage", "Flat"]] = None,
                 skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(staff)):
    q = db.query(Coupon)
    if user.role == OWNER:
        q = q.filter(Coupon.restaurant_id.in_(db.query(Restaurant.id).filter(Restaurant.owner_id == user.id)))
    if restaurant_id is not None:
        q = q.filter(Coupon.restaurant_id == restaurant_id)
    if is_active is not None:
        q = q.filter(Coupon.is_active.is_(is_active))
    if discount_type:
        q = q.filter(Coupon.discount_type == discount_type)
    total = q.count()
    return {"total": total, "skip": skip, "limit": limit,
            "items": [row_dict(c) for c in q.order_by(Coupon.id.desc()).offset(skip).limit(limit)]}


@router.put("/{coupon_id}")
def update_coupon(coupon_id: int, data: CouponUpdate, db: Session = Depends(get_db), user: User = Depends(staff)):
    c = db.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "Coupon not found")
    _check_manage(db, c, user)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    if c.valid_to <= c.valid_from:
        raise HTTPException(422, "valid_to must be after valid_from")
    if c.discount_type == "Percentage" and not (1 <= c.discount_value <= 100):
        raise HTTPException(422, "Percentage coupons must have discount_value between 1 and 100")
    db.commit()
    return row_dict(c)


@router.put("/{coupon_id}/deactivate")
def deactivate_coupon(coupon_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    c = db.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "Coupon not found")
    _check_manage(db, c, user)
    c.is_active = False
    db.commit()
    return row_dict(c)
