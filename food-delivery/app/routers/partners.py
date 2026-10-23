from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.security import PARTNER, require_roles
from app.database import get_db
from app.models import Delivery, DeliveryOffer, DeliveryPartner, Order, User
from app.schemas.schemas import AvailabilityToggleIn, DeliverIn, LocationIn
from app.services import assignment_service
from app.services.order_service import (broadcast_order, change_status, get_order_or_404, notify_admin, order_dict)
from app.utils.common import row_dict
from app.utils.pricing import partner_earning
from app.utils.timeutil import now

router = APIRouter(tags=["Delivery Partner"])
partner_user = require_roles(PARTNER, approved=True)


def get_partner(db: Session, user: User, lock: bool = False) -> DeliveryPartner:
    q = db.query(DeliveryPartner).filter(DeliveryPartner.user_id == user.id)
    p = (q.with_for_update() if lock else q).first()
    if not p:
        raise HTTPException(404, "Delivery partner profile not found")
    return p


def save_location(db: Session, user: User, lat: float, lng: float) -> dict:
    """Shared by PUT /partners/me/location and the /ws/partner socket."""
    p = get_partner(db, user)
    p.current_latitude, p.current_longitude, p.last_location_at = lat, lng, now()
    active = db.query(Order).filter(Order.delivery_partner_id == p.id,
                                    Order.status.in_(["Accepted", "Preparing", "Ready for Pickup",
                                                      "Picked Up", "Out for Delivery"])).all()
    db.commit()
    for o in active:  # push new location + distance remaining + ETA to the order's room
        broadcast_order(o, "Partner location updated")
    return {"latitude": lat, "longitude": lng, "last_location_at": p.last_location_at}


@router.put("/partners/me/availability")
def set_availability(data: AvailabilityToggleIn, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    p = get_partner(db, user)
    if not data.is_online:
        busy = db.query(Delivery).filter(Delivery.partner_id == p.id, Delivery.status == "Active").first()
        if busy:
            raise HTTPException(400, "Finish your active delivery before going offline")
    p.is_online = data.is_online
    db.commit()
    return {"is_online": p.is_online}


@router.put("/partners/me/location")
def update_location(data: LocationIn, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    return save_location(db, user, data.latitude, data.longitude)


@router.get("/partners/me/offers")
def my_offers(db: Session = Depends(get_db), user: User = Depends(partner_user)):
    p = get_partner(db, user)
    offers = db.query(DeliveryOffer).filter(DeliveryOffer.partner_id == p.id, DeliveryOffer.status == "Pending",
                                            DeliveryOffer.expires_at > now()).all()
    return [assignment_service.offer_payload(o, p) for o in offers]


def _lock_offer(db: Session, offer_id: int, p: DeliveryPartner) -> DeliveryOffer:
    offer = db.query(DeliveryOffer).filter(DeliveryOffer.id == offer_id).with_for_update().first()
    if not offer or offer.partner_id != p.id:
        raise HTTPException(404, "Offer not found")
    if offer.status != "Pending":
        raise HTTPException(409, f"Offer is already {offer.status}")
    return offer


@router.put("/offers/{offer_id}/accept")
def accept_offer(offer_id: int, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    p = get_partner(db, user, lock=True)  # lock partner row -> one active delivery at a time
    offer = _lock_offer(db, offer_id, p)
    order = get_order_or_404(db, offer.order_id, lock=True)  # lock order row -> only one partner wins
    if offer.expires_at <= now():
        offer.status = "Expired"
        db.commit()
        raise HTTPException(400, "This offer has expired")
    if order.delivery_partner_id is not None:
        offer.status = "Expired"
        db.commit()
        raise HTTPException(409, "This order has already been assigned to another partner")
    if order.status not in ("Accepted", "Preparing", "Ready for Pickup"):
        raise HTTPException(400, "This order is no longer available")
    if db.query(Delivery).filter(Delivery.partner_id == p.id, Delivery.status == "Active").first():
        raise HTTPException(409, "You already have an active delivery")
    offer.status = "Accepted"
    order.delivery_partner_id = p.id
    db.add(Delivery(order_id=order.id, partner_id=p.id, status="Active", distance_km=order.distance_km,
                    earnings=partner_earning(order.distance_km, order.tip_amount), assigned_at=now()))
    for other in db.query(DeliveryOffer).filter(DeliveryOffer.order_id == order.id, DeliveryOffer.id != offer.id,
                                                DeliveryOffer.status == "Pending"):
        other.status = "Expired"
    db.commit()
    broadcast_order(order, "A delivery partner has been assigned")
    return order_dict(order, user, detail=True)


@router.put("/offers/{offer_id}/decline")
def decline_offer(offer_id: int, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    p = get_partner(db, user)
    offer = _lock_offer(db, offer_id, p)
    offer.status = "Declined"
    order_id = offer.order_id
    db.commit()
    assignment_service.assign_next_partner(db, order_id)  # next nearest partner
    return {"message": "Offer declined"}


# ---------------- Delivery steps ----------------
def _my_order(db: Session, order_id: int, user: User, expected: str):
    p = get_partner(db, user)
    order = get_order_or_404(db, order_id, lock=True)
    if order.delivery_partner_id != p.id:
        raise HTTPException(403, "This order is not assigned to you")
    if order.status != expected:
        raise HTTPException(400, f"Order must be '{expected}' for this action (current: '{order.status}')")
    return p, order


@router.put("/orders/{order_id}/pickup")
def pickup(order_id: int, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    _, order = _my_order(db, order_id, user, "Ready for Pickup")
    change_status(db, order, "Picked Up", user)
    db.commit()
    broadcast_order(order, "Order picked up")
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/out-for-delivery")
def out_for_delivery(order_id: int, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    _, order = _my_order(db, order_id, user, "Picked Up")
    change_status(db, order, "Out for Delivery", user)
    db.commit()
    broadcast_order(order, "Your order is out for delivery")
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/deliver")
def deliver(order_id: int, data: DeliverIn, db: Session = Depends(get_db), user: User = Depends(partner_user)):
    p, order = _my_order(db, order_id, user, "Out for Delivery")
    if order.delivery_locked:
        raise HTTPException(403, "Delivery is locked after 3 wrong OTP attempts. Admin has been notified")
    if data.otp != order.delivery_otp:
        order.otp_attempts += 1
        remaining = 3 - order.otp_attempts
        if order.otp_attempts >= 3:
            order.delivery_locked = True
            notify_admin(db, f"Delivery for {order.order_number} locked after 3 wrong OTP attempts", order.id)
        db.commit()  # persist the attempt, then report the error
        raise HTTPException(400, "Wrong OTP. Delivery locked and admin notified" if remaining <= 0
                            else f"Wrong OTP. {remaining} attempt(s) left")
    change_status(db, order, "Delivered", user)
    order.delivered_at = now()
    if order.payment_method == "COD":
        order.payment_status = "Paid"
    d = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    d.status, d.completed_at = "Completed", now()
    d.earnings = partner_earning(order.distance_km, order.tip_amount)
    db.commit()
    broadcast_order(order, "Order delivered. Enjoy your meal!")
    return order_dict(order, user, detail=True)


@router.get("/partners/me/earnings")
def earnings(from_date: Optional[date] = None, to_date: Optional[date] = None, db: Session = Depends(get_db),
             user: User = Depends(partner_user)):
    p = get_partner(db, user)

    def summary(start: datetime, end: datetime):
        count, total = db.query(func.count(Delivery.id), func.coalesce(func.sum(Delivery.earnings), 0)).filter(
            Delivery.partner_id == p.id, Delivery.status == "Completed",
            Delivery.completed_at >= start, Delivery.completed_at <= end).one()
        return {"deliveries": count, "earnings": round(float(total), 2)}

    today = date.today()
    out = {"today": {"date": today, **summary(datetime.combine(today, time.min), datetime.combine(today, time.max))}}
    if from_date or to_date:
        f, t = from_date or date(2000, 1, 1), to_date or today
        out["range"] = {"from_date": f, "to_date": t,
                        **summary(datetime.combine(f, time.min), datetime.combine(t, time.max))}
    return out
