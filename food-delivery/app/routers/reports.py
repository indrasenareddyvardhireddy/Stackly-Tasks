from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, OWNER, PARTNER, require_roles
from app.database import get_db
from app.models import Delivery, DeliveryPartner, Order, OrderItem, Restaurant, User

router = APIRouter(prefix="/reports", tags=["Reports"])
EXCLUDED = ["Cancelled", "Rejected"]


def _range(from_date: Optional[date], to_date: Optional[date], days: int = 30):
    to_date = to_date or date.today()
    from_date = from_date or to_date - timedelta(days=days)
    if from_date > to_date:
        raise HTTPException(422, "from_date must not be after to_date")
    return datetime.combine(from_date, time.min), datetime.combine(to_date, time.max)


@router.get("/admin-dashboard")
def admin_dashboard(db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    start, end = datetime.combine(date.today(), time.min), datetime.combine(date.today(), time.max)
    today = db.query(Order).filter(Order.placed_at >= start, Order.placed_at <= end)
    by = lambda s: today.filter(Order.status == s).count()  # noqa: E731
    delivered = today.filter(Order.status == "Delivered").all()
    mins = [(o.delivered_at - o.placed_at).total_seconds() / 60 for o in delivered if o.delivered_at]
    return {
        "date": date.today(), "total_orders": today.count(), "delivered_orders": len(delivered),
        "cancelled_orders": by("Cancelled"), "rejected_orders": by("Rejected"),
        "total_revenue": round(sum(o.grand_total for o in delivered), 2),
        "total_discount_given": round(float(today.filter(~Order.status.in_(EXCLUDED)).with_entities(
            func.coalesce(func.sum(Order.discount_amount), 0)).scalar()), 2),
        "online_partners": db.query(DeliveryPartner).filter(DeliveryPartner.is_online.is_(True)).count(),
        "average_delivery_minutes": round(sum(mins) / len(mins), 1) if mins else 0,
    }


@router.get("/top-restaurants")
def top_restaurants(from_date: Optional[date] = None, to_date: Optional[date] = None,
                    db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    start, end = _range(from_date, to_date)
    rows = (db.query(Restaurant.id, Restaurant.name, func.count(Order.id), func.coalesce(func.sum(Order.grand_total), 0))
            .join(Order, Order.restaurant_id == Restaurant.id)
            .filter(Order.status == "Delivered", Order.placed_at >= start, Order.placed_at <= end)
            .group_by(Restaurant.id, Restaurant.name)
            .order_by(func.count(Order.id).desc(), func.sum(Order.grand_total).desc()).limit(10).all())
    return [{"restaurant_id": i, "name": n, "orders": c, "revenue": round(float(r), 2)} for i, n, c, r in rows]


@router.get("/coupon-usage")
def coupon_usage(from_date: Optional[date] = None, to_date: Optional[date] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_roles(ADMIN, OWNER, approved=True))):
    start, end = _range(from_date, to_date)
    q = (db.query(Order.coupon_code, func.count(Order.id), func.sum(Order.discount_amount), func.sum(Order.grand_total))
         .filter(Order.coupon_code.isnot(None), ~Order.status.in_(EXCLUDED),
                 Order.placed_at >= start, Order.placed_at <= end))
    if user.role == OWNER:
        q = q.filter(Order.restaurant_id.in_(db.query(Restaurant.id).filter(Restaurant.owner_id == user.id)))
    return [{"coupon_code": c, "times_used": n, "total_discount_given": round(float(d or 0), 2),
             "revenue_from_orders": round(float(r or 0), 2)} for c, n, d, r in q.group_by(Order.coupon_code).all()]


@router.get("/restaurant-sales")
def restaurant_sales(restaurant_id: Optional[int] = None, from_date: Optional[date] = None,
                     to_date: Optional[date] = None, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(ADMIN, OWNER, approved=True))):  # CHANGED: added ADMIN
    start, end = _range(from_date, to_date, days=7)
    mine = db.query(Restaurant.id)
    if user.role == OWNER:  # CHANGED: owners are limited to their own restaurants, admin sees all
        mine = mine.filter(Restaurant.owner_id == user.id)
    if restaurant_id:
        if user.role == OWNER and not db.query(Restaurant).filter(
                Restaurant.id == restaurant_id, Restaurant.owner_id == user.id).first():
            raise HTTPException(403, "You can view reports only for your own restaurants")
        mine = mine.filter(Restaurant.id == restaurant_id)
    ids = [r[0] for r in mine.all()]
    base = db.query(Order).filter(Order.restaurant_id.in_(ids), Order.status == "Delivered",
                                  Order.placed_at >= start, Order.placed_at <= end)
    daily = (base.with_entities(func.date(Order.placed_at), func.count(Order.id), func.sum(Order.item_total))
             .group_by(func.date(Order.placed_at)).order_by(func.date(Order.placed_at)).all())
    best = (db.query(OrderItem.item_name, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.restaurant_id.in_(ids), Order.status == "Delivered",
                    Order.placed_at >= start, Order.placed_at <= end)
            .group_by(OrderItem.item_name).order_by(func.sum(OrderItem.quantity).desc()).limit(5).all())
    preps = [(o.ready_at - o.accepted_at).total_seconds() / 60 for o in base.all() if o.ready_at and o.accepted_at]
    return {"daily_sales": [{"date": d, "orders": c, "sales": round(float(s or 0), 2)} for d, c, s in daily],
            "total_orders": base.count(),
            "best_selling_items": [{"item": n, "quantity": int(q)} for n, q in best],
            "average_preparation_minutes": round(sum(preps) / len(preps), 1) if preps else 0}


@router.get("/partner-summary")
def partner_summary(partner_id: Optional[int] = None, from_date: Optional[date] = None,  # CHANGED: added partner_id
                    to_date: Optional[date] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(ADMIN, PARTNER, approved=True))):  # CHANGED: added ADMIN
    start, end = _range(from_date, to_date)
    if user.role == PARTNER:  # partners always see only themselves, partner_id is ignored
        p = db.query(DeliveryPartner).filter(DeliveryPartner.user_id == user.id).first()
        if not p:
            raise HTTPException(404, "Delivery partner profile not found")
        pid = p.id
    else:  # admin must say which partner
        if partner_id is None:
            raise HTTPException(422, "partner_id is required for admin")
        pid = partner_id
    rows = (db.query(func.date(Delivery.completed_at), func.count(Delivery.id), func.sum(Delivery.distance_km),
                     func.sum(Delivery.earnings))
            .filter(Delivery.partner_id == pid, Delivery.status == "Completed",  # CHANGED: p.id -> pid
                    Delivery.completed_at >= start, Delivery.completed_at <= end)
            .group_by(func.date(Delivery.completed_at)).order_by(func.date(Delivery.completed_at)).all())
    days = [{"date": d, "deliveries": c, "distance_km": round(float(km or 0), 2), "earnings": round(float(e or 0), 2)}
            for d, c, km, e in rows]
    return {"deliveries_completed": sum(d["deliveries"] for d in days),
            "total_distance_km": round(sum(d["distance_km"] for d in days), 2),
            "total_earnings": round(sum(d["earnings"] for d in days), 2), "by_day": days}