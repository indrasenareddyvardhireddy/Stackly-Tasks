from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Coupon, CouponUsage, Order
from app.utils.timeutil import now


def _money(x: float) -> str:
    return f"₹{int(x)}" if float(x).is_integer() else f"₹{x:.2f}"


def find_coupon(db: Session, code: str, lock: bool = False) -> Coupon:
    q = db.query(Coupon).filter(func.upper(Coupon.code) == code.strip().upper())  # case-insensitive
    if lock:
        q = q.with_for_update()
    coupon = q.first()
    if not coupon:
        raise HTTPException(400, "Invalid coupon code")
    return coupon


def compute_discount(coupon: Coupon, item_total: float) -> float:
    if coupon.discount_type == "Percentage":
        d = item_total * coupon.discount_value / 100
        if coupon.max_discount is not None:
            d = min(d, coupon.max_discount)
    else:
        d = coupon.discount_value
    return round(max(0.0, min(d, item_total)), 2)  # never more than the item total


def validate_coupon(db: Session, coupon: Coupon, user_id: int, restaurant_id: int, item_total: float) -> float:
    """Raises HTTP 400 with a clear reason, otherwise returns the discount amount."""
    t = now()
    if not coupon.is_active:
        raise HTTPException(400, "This coupon is not active")
    if t < coupon.valid_from:
        raise HTTPException(400, "This coupon is not valid yet")
    if t > coupon.valid_to:
        raise HTTPException(400, "This coupon has expired")
    if coupon.restaurant_id is not None and coupon.restaurant_id != restaurant_id:
        raise HTTPException(400, "This coupon is not valid for this restaurant")
    if item_total < coupon.min_order_value:
        raise HTTPException(400, f"Minimum order value is {_money(coupon.min_order_value)}")
    used = db.query(func.count(CouponUsage.id)).filter(
        CouponUsage.coupon_id == coupon.id, CouponUsage.is_released.is_(False)).scalar()
    if coupon.total_usage_limit is not None and used >= coupon.total_usage_limit:
        raise HTTPException(400, "This coupon has reached its usage limit")
    if coupon.per_user_limit is not None:
        mine = db.query(func.count(CouponUsage.id)).filter(
            CouponUsage.coupon_id == coupon.id, CouponUsage.user_id == user_id,
            CouponUsage.is_released.is_(False)).scalar()
        if mine >= coupon.per_user_limit:
            raise HTTPException(400, "You have already used this coupon the maximum number of times")
    if coupon.first_order_only:
        delivered = db.query(func.count(Order.id)).filter(
            Order.customer_id == user_id, Order.status == "Delivered").scalar()
        if delivered:
            raise HTTPException(400, "This coupon is valid only on your first order")
    return compute_discount(coupon, item_total)


def release_usage(db: Session, order: Order):
    for u in db.query(CouponUsage).filter(CouponUsage.order_id == order.id, CouponUsage.is_released.is_(False)):
        u.is_released = True
        u.released_at = now()
