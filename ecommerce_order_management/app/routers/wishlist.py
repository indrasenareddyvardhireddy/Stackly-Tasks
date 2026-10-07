from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.wishlist import WishlistItem
from app.models.product import Product
from app.models.user import UserRole
from app.auth.dependencies import require_role
from app.schemas.product import ProductResponse
router=APIRouter(prefix="/wishlist",tags=["Wishlist"])

@router.get("",response_model=list[ProductResponse])
def list_wishlist(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    return db.scalars(select(Product).join(WishlistItem).where(WishlistItem.customer_id==user.id)).all()

@router.post("/{product_id}")
def add(product_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    p=db.scalar(select(Product).where(Product.id==product_id,Product.is_active==True))
    if not p: raise HTTPException(404,"Product not found")
    if db.scalar(select(WishlistItem).where(WishlistItem.customer_id==user.id,WishlistItem.product_id==product_id)):
        raise HTTPException(409,"Product already in wishlist")
    db.add(WishlistItem(customer_id=user.id,product_id=product_id)); db.commit(); return {"message":"Added to wishlist"}

@router.delete("/{product_id}")
def remove(product_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    x=db.scalar(select(WishlistItem).where(WishlistItem.customer_id==user.id,WishlistItem.product_id==product_id))
    if not x: raise HTTPException(404,"Wishlist item not found")
    db.delete(x); db.commit(); return {"message":"Removed from wishlist"}
