from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Cart, Restaurant
from app.services.coupon_service import validate_coupon


def get_or_create_cart(db: Session, user) -> Cart:
    cart = db.query(Cart).filter(Cart.customer_id == user.id).first()
    if not cart:
        cart = Cart(customer_id=user.id)
        db.add(cart)
        db.flush()
    return cart


def cart_totals(cart: Cart):
    item_total = round(sum(i.menu_item.price * i.quantity for i in cart.items), 2)
    packaging = round(sum(i.menu_item.packaging_charge * i.quantity for i in cart.items), 2)
    return item_total, packaging


def cart_view(db: Session, cart: Cart) -> dict:
    item_total, packaging = cart_totals(cart)
    restaurant = db.get(Restaurant, cart.restaurant_id) if cart.restaurant_id else None
    discount, coupon_info, coupon_error = 0.0, None, None
    if cart.coupon_id and cart.items:
        try:
            discount = validate_coupon(db, cart.coupon, cart.customer_id, cart.restaurant_id, item_total)
            coupon_info = {"code": cart.coupon.code, "description": cart.coupon.description}
        except HTTPException as e:  # coupon became invalid after it was applied
            coupon_error = e.detail
    return {
        "cart_id": cart.id,
        "restaurant": {"id": restaurant.id, "name": restaurant.name} if restaurant else None,
        "items": [{
            "item_id": i.id, "menu_item_id": i.menu_item_id, "name": i.menu_item.name,
            "is_available": i.menu_item.is_available and not i.menu_item.is_deleted,
            "price": i.menu_item.price, "quantity": i.quantity,
            "line_total": round(i.menu_item.price * i.quantity, 2)} for i in cart.items],
        "item_total": item_total,
        "applied_coupon": coupon_info,
        "coupon_error": coupon_error,
        "discount": discount,
        "item_total_after_discount": round(item_total - discount, 2),
    }


def reset_cart_if_empty(cart: Cart):
    if not cart.items:
        cart.restaurant_id = None
        cart.coupon_id = None
