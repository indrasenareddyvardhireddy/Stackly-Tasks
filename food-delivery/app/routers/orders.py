from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.security import CUSTOMER, OWNER, require_roles
from app.database import get_db
from app.models import CartItem, MenuItem, Order, Restaurant, User
from app.schemas.schemas import AcceptIn, CancelIn, OrderIn, RejectIn
from app.services import assignment_service
from app.services.cart_service import cart_view, get_or_create_cart
from app.services.order_service import (broadcast_order, can_view_order, change_status, get_order_or_404,
                                        order_dict, place_order, reject_or_cancel)
from app.utils.timeutil import now

router = APIRouter()


def _paginate_orders(q, user, skip, limit):
    total = q.count()
    rows = q.order_by(Order.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": [order_dict(o, user) for o in rows]}


# ---------------- Customer order endpoints (customer role only) ----------------
@router.post("/orders", status_code=201, tags=["Orders"])
def create_order(data: OrderIn, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    return order_dict(place_order(db, user, data), user, detail=True)


@router.get("/orders", tags=["Orders"])
def list_orders(status: Optional[str] = None, restaurant_id: Optional[int] = None,
                from_date: Optional[date] = None, to_date: Optional[date] = None,
                skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    q = db.query(Order).filter(Order.customer_id == user.id)  # a customer sees only their own orders
    if status:
        q = q.filter(Order.status == status)
    if restaurant_id:
        q = q.filter(Order.restaurant_id == restaurant_id)
    if from_date:
        q = q.filter(Order.placed_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.filter(Order.placed_at <= datetime.combine(to_date, time.max))
    return _paginate_orders(q, user, skip, limit)


@router.get("/restaurants/me/orders", tags=["Restaurant Order Handling"])
def restaurant_orders(status: Optional[str] = None, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                      db: Session = Depends(get_db), user: User = Depends(require_roles(OWNER))):
    q = db.query(Order).filter(Order.restaurant_id.in_(db.query(Restaurant.id).filter(Restaurant.owner_id == user.id)))
    if status:
        q = q.filter(Order.status == status)
    return _paginate_orders(q, user, skip, limit)


@router.get("/orders/{order_id}", tags=["Orders"])
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    order = get_order_or_404(db, order_id)
    if not can_view_order(user, order):
        raise HTTPException(403, "You cannot view this order")
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/cancel", tags=["Orders"])
def cancel_order(order_id: int, data: Optional[CancelIn] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_roles(CUSTOMER))):
    order = get_order_or_404(db, order_id, lock=True)
    if order.customer_id != user.id:
        raise HTTPException(403, "You can cancel only your own orders")
    if order.status != "Placed":
        raise HTTPException(400, "Order can be cancelled only while it is Placed")
    reject_or_cancel(db, order, "Cancelled", user, data.reason if data else None)
    db.commit()
    broadcast_order(order, "Order cancelled")
    return order_dict(order, user, detail=True)


@router.post("/orders/{order_id}/reorder", tags=["Orders"])
def reorder(order_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    order = get_order_or_404(db, order_id)
    if order.customer_id != user.id:
        raise HTTPException(403, "You can reorder only your own orders")
    cart = get_or_create_cart(db, user)
    if cart.items and cart.restaurant_id != order.restaurant_id:
        raise HTTPException(409, "Your cart has items from another restaurant. Clear the cart to continue")
    skipped, added = [], 0
    for oi in order.items:
        m = db.get(MenuItem, oi.menu_item_id)
        if not m or m.is_deleted or not m.is_available:
            skipped.append(oi.item_name)
            continue
        existing = next((i for i in cart.items if i.menu_item_id == m.id), None)
        if existing:
            existing.quantity = min(10, existing.quantity + oi.quantity)
        else:
            cart.items.append(CartItem(menu_item_id=m.id, quantity=min(10, oi.quantity)))
        added += 1
    if added:
        cart.restaurant_id = order.restaurant_id
    cart.coupon_id = None  # the old coupon is not re-applied
    db.commit()
    db.refresh(cart)
    return {"cart": cart_view(db, cart), "skipped_unavailable_items": skipped}


# ---------------- Restaurant order handling (Level 8) ----------------
def _owned_order(db: Session, order_id: int, user: User) -> Order:
    order = get_order_or_404(db, order_id, lock=True)
    if order.restaurant.owner_id != user.id:
        raise HTTPException(403, "Only the owner of this order's restaurant can update it")
    return order


def _expect(order: Order, status: str):
    if order.status != status:
        raise HTTPException(400, f"Order must be '{status}' for this action (current: '{order.status}')")


owner = require_roles(OWNER, approved=True)


@router.put("/orders/{order_id}/accept", tags=["Restaurant Order Handling"])
def accept_order(order_id: int, data: AcceptIn, db: Session = Depends(get_db), user: User = Depends(owner)):
    order = _owned_order(db, order_id, user)
    _expect(order, "Placed")
    order.estimated_prep_minutes = data.estimated_preparation_minutes
    order.accepted_at = now()
    change_status(db, order, "Accepted", user)
    db.commit()
    broadcast_order(order, "Restaurant accepted your order")
    assignment_service.assign_next_partner(db, order.id)  # start delivery partner assignment
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/reject", tags=["Restaurant Order Handling"])
def reject_order(order_id: int, data: RejectIn, db: Session = Depends(get_db), user: User = Depends(owner)):
    order = _owned_order(db, order_id, user)
    _expect(order, "Placed")
    reject_or_cancel(db, order, "Rejected", user, data.reason)
    db.commit()
    broadcast_order(order, f"Order rejected: {data.reason}")
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/preparing", tags=["Restaurant Order Handling"])
def mark_preparing(order_id: int, db: Session = Depends(get_db), user: User = Depends(owner)):
    order = _owned_order(db, order_id, user)
    _expect(order, "Accepted")
    change_status(db, order, "Preparing", user)
    db.commit()
    broadcast_order(order, "Your food is being prepared")
    return order_dict(order, user, detail=True)


@router.put("/orders/{order_id}/ready", tags=["Restaurant Order Handling"])
def mark_ready(order_id: int, db: Session = Depends(get_db), user: User = Depends(owner)):
    order = _owned_order(db, order_id, user)
    _expect(order, "Preparing")
    order.ready_at = now()
    change_status(db, order, "Ready for Pickup", user)
    db.commit()
    broadcast_order(order, "Order is ready for pickup")
    return order_dict(order, user, detail=True)