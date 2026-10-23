import math
import secrets
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (Address, Cart, Coupon, CouponUsage, Notification, Order, OrderItem,
                        OrderStatusHistory, Restaurant)
from app.services.cart_service import cart_totals
from app.services.coupon_service import release_usage, validate_coupon
from app.services.restaurant_service import restaurant_is_open
from app.utils.common import ACTIVE_ORDER_STATUSES as ACTIVE_STATUSES, row_dict
from app.utils.geo import haversine_km, travel_minutes
from app.utils.pricing import calculate_bill
from app.utils.timeutil import now
from app.websockets.manager import manager


# ---------- history / status ----------
def actor_name(user) -> str:
    return "System" if user is None else f"{user.role}:{user.id}"


def change_status(db: Session, order: Order, new_status: str, user=None, note: str = None):
    """Single place where status changes happen -> always recorded in history."""
    db.add(OrderStatusHistory(order_id=order.id, old_status=order.status, new_status=new_status,
                              changed_by=actor_name(user), note=note, changed_at=now()))
    order.status = new_status


def refund_and_release(db: Session, order: Order):
    if order.payment_method == "Online" and order.payment_status == "Paid":
        order.payment_status = "Refunded"
    release_usage(db, order)


def notify_admin(db: Session, message: str, order_id: int = None):
    db.add(Notification(target_role="admin", message=message, order_id=order_id))


# ---------- live payloads ----------
def tracking_payload(order: Order, message: str = None) -> dict:
    data = {"type": "order_update", "order_id": order.id, "order_number": order.order_number,
            "status": order.status, "message": message, "payment_status": order.payment_status,
            "updated_at": now().isoformat()}
    p = order.partner
    remaining = order.distance_km
    if p:
        data["partner"] = {"name": p.user.name, "vehicle_type": p.vehicle_type,
                           "vehicle_number": p.vehicle_number,
                           "latitude": p.current_latitude, "longitude": p.current_longitude,
                           "last_location_at": p.last_location_at.isoformat() if p.last_location_at else None}
        if p.current_latitude is not None:
            if order.status in ("Picked Up", "Out for Delivery"):
                remaining = haversine_km(p.current_latitude, p.current_longitude,
                                         order.address.latitude, order.address.longitude)
            else:
                remaining = (haversine_km(p.current_latitude, p.current_longitude,
                                          order.restaurant.latitude, order.restaurant.longitude)
                             + order.distance_km)
    eta = travel_minutes(remaining)
    if order.status in ("Placed", "Accepted", "Preparing") and order.accepted_at and order.estimated_prep_minutes:
        left = order.estimated_prep_minutes - (now() - order.accepted_at).total_seconds() / 60
        eta += max(0.0, left)
    elif order.status == "Placed":
        eta += order.restaurant.avg_preparation_minutes
    if order.status in ("Delivered", "Rejected", "Cancelled"):
        eta, remaining = 0, 0
    data["distance_remaining_km"] = round(remaining, 2)
    data["eta_minutes"] = math.ceil(eta)
    return data


def broadcast_order(order: Order, message: str = None):
    """Call AFTER commit."""
    manager.push("orders", order.id, tracking_payload(order, message))


def order_dict(order: Order, viewer=None, detail=False) -> dict:
    hide = ("otp_attempts", "delivery_locked") if not (viewer and viewer.role == "admin") else ()
    show_otp = viewer is not None and viewer.id == order.customer_id
    d = row_dict(order, exclude=hide + (() if show_otp else ("delivery_otp",)))
    d["restaurant_name"] = order.restaurant.name
    if detail:
        d["items"] = [row_dict(i) for i in order.items]
        d["history"] = [row_dict(h) for h in order.history]
        d["address"] = row_dict(order.address)
        if order.partner:
            d["delivery_partner"] = {"name": order.partner.user.name, "vehicle_type": order.partner.vehicle_type,
                                     "vehicle_number": order.partner.vehicle_number}
    return d


def push_new_order(order: Order):
    manager.push("restaurants", order.restaurant.owner_id, {
        "type": "new_order", **{k: order_dict(order, detail=False)[k] for k in
                                ("id", "order_number", "item_total", "grand_total", "payment_method", "status",
                                 "placed_at", "distance_km")},
        "customer_name": order.customer.name,
        "items": [{"name": i.item_name, "quantity": i.quantity, "price": i.price} for i in order.items]})


# ---------- access ----------
def can_view_order(user, order: Order) -> bool:
    if user.role == "admin" or user.id == order.customer_id:
        return True
    if user.role == "restaurant_owner" and order.restaurant.owner_id == user.id:
        return True
    return bool(user.role == "delivery_partner" and order.partner and order.partner.user_id == user.id)


def get_order_or_404(db: Session, order_id: int, lock: bool = False) -> Order:
    q = db.query(Order).filter(Order.id == order_id)
    if lock:
        q = q.with_for_update()
    order = q.first()
    if not order:
        raise HTTPException(404, "Order not found")
    return order


# ---------- placement ----------
def _next_order_number(db: Session) -> str:
    today = date.today()
    count = db.query(func.count(Order.id)).filter(func.date(Order.placed_at) == today).scalar()
    return f"ORD-{today:%Y%m%d}-{count + 1:04d}"


def place_order(db: Session, user, payload) -> Order:
    """Everything below runs in ONE transaction; any failure rolls everything back."""
    try:
        cart = db.query(Cart).filter(Cart.customer_id == user.id).with_for_update().first()
        if not cart or not cart.items:
            raise HTTPException(400, "Cart is empty")
        restaurant = db.get(Restaurant, cart.restaurant_id)
        if not restaurant_is_open(restaurant):
            raise HTTPException(400, "Restaurant is currently closed")
        address = db.get(Address, payload.address_id)
        if not address or address.customer_id != user.id:
            raise HTTPException(404, "Address not found")
        distance = round(haversine_km(restaurant.latitude, restaurant.longitude,
                                      address.latitude, address.longitude), 2)
        if distance > restaurant.delivery_radius_km:
            raise HTTPException(400, "Delivery address is outside the restaurant's delivery radius")
        for ci in cart.items:
            if ci.menu_item.is_deleted or not ci.menu_item.is_available:
                raise HTTPException(400, f"'{ci.menu_item.name}' is no longer available")
        item_total, packaging = cart_totals(cart)
        if item_total < restaurant.min_order_value:
            raise HTTPException(400, f"Minimum order value is ₹{restaurant.min_order_value:g}")

        discount, coupon = 0.0, None
        if cart.coupon_id:  # re-validate under a row lock (usage limits may have been reached)
            coupon = db.query(Coupon).filter(Coupon.id == cart.coupon_id).with_for_update().first()
            discount = validate_coupon(db, coupon, user.id, restaurant.id, item_total)

        placed = now()
        bill = calculate_bill(item_total, discount, packaging, distance, payload.tip_amount, placed)
        order = Order(
            order_number=_next_order_number(db), customer_id=user.id, restaurant_id=restaurant.id,
            address_id=address.id, coupon_code=coupon.code if coupon else None, distance_km=distance,
            payment_method=payload.payment_method,
            payment_status="Paid" if payload.payment_method == "Online" else "Pending",  # online = mock
            status="Placed", delivery_otp=f"{secrets.randbelow(10000):04d}", placed_at=placed, **bill)
        db.add(order)
        db.flush()
        for ci in cart.items:
            m = ci.menu_item
            db.add(OrderItem(order_id=order.id, menu_item_id=m.id, item_name=m.name, price=m.price,
                             packaging_charge=m.packaging_charge, quantity=ci.quantity,
                             line_total=round(m.price * ci.quantity, 2)))
        db.add(OrderStatusHistory(order_id=order.id, old_status=None, new_status="Placed",
                                  changed_by=actor_name(user), changed_at=placed))
        if coupon:
            db.add(CouponUsage(coupon_id=coupon.id, user_id=user.id, order_id=order.id, discount_amount=discount))
        for ci in list(cart.items):  # clear cart
            db.delete(ci)
        cart.restaurant_id = None
        cart.coupon_id = None
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Could not place order due to a conflict, please retry")
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    push_new_order(order)
    return order


def reject_or_cancel(db: Session, order: Order, new_status: str, user, reason: str = None):
    """Used for Rejected / Cancelled (manual and automatic)."""
    change_status(db, order, new_status, user, reason)
    if new_status == "Rejected":
        order.rejection_reason = reason
    refund_and_release(db, order)
