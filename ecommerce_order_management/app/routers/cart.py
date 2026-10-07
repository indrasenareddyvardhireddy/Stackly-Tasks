from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.cart import Cart,CartItem
from app.models.product import Product
from app.schemas.cart import CartItemCreate,CartItemUpdate,CartResponse
from app.auth.dependencies import require_role
from app.models.user import UserRole

router=APIRouter(prefix="/cart",tags=["Cart"])

def get_cart(db,user):
    cart=db.scalar(select(Cart).where(Cart.customer_id==user.id))
    if not cart:
        cart=Cart(customer_id=user.id); db.add(cart); db.commit(); db.refresh(cart)
    return cart

def response(cart):
    items=[]; subtotal=Decimal("0")
    for i in cart.items:
        line=i.product.price*i.quantity; subtotal+=line
        items.append({"id":i.id,"product_id":i.product_id,"product_name":i.product.name,"quantity":i.quantity,"price":i.product.price,"line_total":line})
    return {"id":cart.id,"items":items,"subtotal":subtotal}

@router.get("",response_model=CartResponse)
def get(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))): return response(get_cart(db,user))

@router.post("/items",response_model=CartResponse)
def add(data:CartItemCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    cart=get_cart(db,user); p=db.get(Product,data.product_id)
    if not p or not p.is_active: raise HTTPException(404,"Active product not found")
    item=db.scalar(select(CartItem).where(CartItem.cart_id==cart.id,CartItem.product_id==p.id))
    qty=(item.quantity if item else 0)+data.quantity
    if qty>p.stock_quantity: raise HTTPException(400,"Quantity exceeds available stock")
    if item: item.quantity=qty
    else: db.add(CartItem(cart_id=cart.id,product_id=p.id,quantity=data.quantity))
    db.commit(); db.refresh(cart); return response(cart)

@router.put("/items/{item_id}",response_model=CartResponse)
def update(item_id:int,data:CartItemUpdate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    cart=get_cart(db,user); item=db.scalar(select(CartItem).where(CartItem.id==item_id,CartItem.cart_id==cart.id))
    if not item: raise HTTPException(404,"Cart item not found")
    if not item.product.is_active: raise HTTPException(400,"Product inactive")
    if data.quantity>item.product.stock_quantity: raise HTTPException(400,"Quantity exceeds available stock")
    item.quantity=data.quantity; db.commit(); return response(cart)

@router.delete("/items/{item_id}")
def remove(item_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    cart=get_cart(db,user); item=db.scalar(select(CartItem).where(CartItem.id==item_id,CartItem.cart_id==cart.id))
    if not item: raise HTTPException(404,"Cart item not found")
    db.delete(item); db.commit(); return {"message":"Cart item removed"}

@router.delete("")
def clear(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    cart=get_cart(db,user)
    for i in list(cart.items): db.delete(i)
    db.commit(); return {"message":"Cart cleared"}
