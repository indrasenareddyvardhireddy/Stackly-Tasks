"""Nearest-partner assignment with 30s offers."""
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Delivery, DeliveryOffer, DeliveryPartner, Order
from app.services.order_service import (ACTIVE_STATUSES, broadcast_order, change_status, notify_admin)
from app.utils.geo import haversine_km
from app.utils.pricing import partner_earning
from app.utils.timeutil import now
from app.websockets.manager import manager

OFFER_SECONDS = 30
SEARCH_RADIUS_KM = 5.0
UNASSIGNED_ALERT_MINUTES = 15


def offer_payload(offer: DeliveryOffer, partner: DeliveryPartner) -> dict:
    order = offer.order
    r = order.restaurant
    pickup = (haversine_km(partner.current_latitude, partner.current_longitude, r.latitude, r.longitude)
              if partner.current_latitude is not None else None)
    return {"type": "delivery_offer", "offer_id": offer.id, "order_id": order.id,
            "order_number": order.order_number, "restaurant_name": r.name, "restaurant_address": r.address,
            "pickup_distance_km": round(pickup, 2) if pickup is not None else None,
            "delivery_distance_km": order.distance_km,
            "expected_earnings": partner_earning(order.distance_km, order.tip_amount),
            "seconds_left": max(0, int((offer.expires_at - now()).total_seconds())),
            "status": offer.status}


def candidates(db: Session, order: Order):
    """Approved, online, no active delivery, no live offer, within 5 km; nearest first."""
    t = now()
    busy = {d.partner_id for d in db.query(Delivery.partner_id).filter(Delivery.status == "Active")}
    pending = {o.partner_id for o in db.query(DeliveryOffer.partner_id).filter(
        DeliveryOffer.status == "Pending", DeliveryOffer.expires_at > t)}
    already = {o.partner_id for o in db.query(DeliveryOffer.partner_id).filter(
        DeliveryOffer.order_id == order.id, DeliveryOffer.status.in_(["Declined", "Expired"]))}
    r = order.restaurant
    found = []
    q = db.query(DeliveryPartner).filter(DeliveryPartner.is_approved.is_(True), DeliveryPartner.is_online.is_(True),
                                         DeliveryPartner.current_latitude.isnot(None))
    for p in q:
        if p.id in busy or p.id in pending or p.id in already:
            continue
        d = haversine_km(p.current_latitude, p.current_longitude, r.latitude, r.longitude)
        if d <= SEARCH_RADIUS_KM:
            found.append((d, p))
    found.sort(key=lambda x: x[0])
    return found


def assign_next_partner(db: Session, order_id: int) -> Optional[DeliveryOffer]:
    """Offer the order to the nearest eligible partner. Commits its own work."""
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()  # serialise concurrent callers
    if (not order or order.status not in ACTIVE_STATUSES or order.delivery_partner_id
            or order.status in ("Picked Up", "Out for Delivery")):
        db.rollback()
        return None
    t = now()
    live = db.query(DeliveryOffer).filter(DeliveryOffer.order_id == order.id, DeliveryOffer.status == "Pending",
                                          DeliveryOffer.expires_at > t).first()
    if live:
        db.rollback()
        return None
    found = candidates(db, order)
    if not found:
        db.rollback()
        return None
    partner = found[0][1]
    offer = DeliveryOffer(order_id=order.id, partner_id=partner.id, status="Pending", offered_at=t,
                          expires_at=t + timedelta(seconds=OFFER_SECONDS))
    db.add(offer)
    db.commit()
    db.refresh(offer)
    manager.push("partners", partner.user_id, offer_payload(offer, partner))
    return offer


def expire_offers(db: Session):
    t = now()
    expired = db.query(DeliveryOffer).filter(DeliveryOffer.status == "Pending", DeliveryOffer.expires_at <= t).all()
    info = [(o.order_id, o.partner.user_id, o.id) for o in expired]
    for o in expired:
        o.status = "Expired"
    db.commit()
    for order_id, user_id, offer_id in info:
        manager.push("partners", user_id, {"type": "offer_expired", "offer_id": offer_id})
    for order_id in {i[0] for i in info}:
        assign_next_partner(db, order_id)


def retry_unassigned(db: Session):
    """Retry orders with no partner; alert admin once after 15 minutes."""
    orders = db.query(Order).filter(Order.status.in_(["Accepted", "Preparing", "Ready for Pickup"]),
                                    Order.delivery_partner_id.is_(None)).all()
    for o in orders:
        oid = o.id
        waited = (now() - o.accepted_at).total_seconds() / 60 if o.accepted_at else 0
        if waited >= UNASSIGNED_ALERT_MINUTES and not o.admin_notified_unassigned:
            o.admin_notified_unassigned = True
            notify_admin(db, f"Order {o.order_number} is still unassigned after {UNASSIGNED_ALERT_MINUTES} minutes", o.id)
            db.commit()
        assign_next_partner(db, oid)
