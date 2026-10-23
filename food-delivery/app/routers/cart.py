from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.security import CUSTOMER, require_roles
from app.database import get_db
from app.models import CartItem, MenuItem, Restaurant, User
from app.schemas.schemas import ApplyCouponIn, CartItemIn, CartItemUpdate
from app.services.cart_service import cart_totals, cart_view, get_or_create_cart, reset_cart_if_empty
from app.services.coupon_service import find_coupon, validate_coupon

router = APIRouter(prefix="/cart", tags=["Cart"])
customer = require_roles(CUSTOMER)


@router.get("")
def get_cart(db: Session = Depends(get_db), user: User = Depends(customer)):
    cart = get_or_create_cart(db, user)
    db.commit()
    return cart_view(db, cart)


@router.post("/items", status_code=201)
def add_item(data: CartItemIn, db: Session = Depends(get_db), user: User = Depends(customer)):
    item = db.get(MenuItem, data.menu_item_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Menu item not found")
    if not item.is_available:
        raise HTTPException(400, "This item is currently unavailable")
    restaurant = db.get(Restaurant, item.restaurant_id)
    if not restaurant.is_active:
        raise HTTPException(400, "Restaurant is not active")
    cart = get_or_create_cart(db, user)
    if cart.items and cart.restaurant_id != item.restaurant_id:
        raise HTTPException(409, "Your cart has items from another restaurant. Clear the cart to continue")
    existing = next((i for i in cart.items if i.menu_item_id == item.id), None)
    if existing:
        if existing.quantity + data.quantity > 10:
            raise HTTPException(400, "Quantity must be between 1 and 10 per item")
        existing.quantity += data.quantity  # same item again -> increase quantity
    else:
        cart.items.append(CartItem(menu_item_id=item.id, quantity=data.quantity))
    cart.restaurant_id = item.restaurant_id
    db.commit()
    db.refresh(cart)
    return cart_view(db, cart)


def _cart_item(db, item_id, user):
    cart = get_or_create_cart(db, user)
    ci = next((i for i in cart.items if i.id == item_id), None)
    if not ci:
        raise HTTPException(404, "Cart item not found")
    return cart, ci


@router.put("/items/{item_id}")
def update_item(item_id: int, data: CartItemUpdate, db: Session = Depends(get_db), user: User = Depends(customer)):
    cart, ci = _cart_item(db, item_id, user)
    ci.quantity = data.quantity
    db.commit()
    db.refresh(cart)
    return cart_view(db, cart)


@router.delete("/items/{item_id}")
def remove_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(customer)):
    cart, ci = _cart_item(db, item_id, user)
    cart.items.remove(ci)
    db.flush()
    reset_cart_if_empty(cart)
    db.commit()
    db.refresh(cart)
    return cart_view(db, cart)


@router.delete("")
def clear_cart(db: Session = Depends(get_db), user: User = Depends(customer)):
    cart = get_or_create_cart(db, user)
    cart.items.clear()
    cart.restaurant_id = None
    cart.coupon_id = None  # clearing the cart also removes the coupon
    db.commit()
    return {"message": "Cart cleared"}


@router.post("/apply-coupon")
def apply_coupon(data: ApplyCouponIn, db: Session = Depends(get_db), user: User = Depends(customer)):
    cart = get_or_create_cart(db, user)
    if not cart.items:
        raise HTTPException(400, "Cart is empty")
    coupon = find_coupon(db, data.code)
    item_total, _ = cart_totals(cart)
    validate_coupon(db, coupon, user.id, cart.restaurant_id, item_total)  # raises 400 with reason
    cart.coupon_id = coupon.id  # only one coupon per order: replaces any previous one
    db.commit()
    db.refresh(cart)
    return cart_view(db, cart)


@router.delete("/coupon")
def remove_coupon(db: Session = Depends(get_db), user: User = Depends(customer)):
    cart = get_or_create_cart(db, user)
    cart.coupon_id = None
    db.commit()
    db.refresh(cart)
    return cart_view(db, cart)
