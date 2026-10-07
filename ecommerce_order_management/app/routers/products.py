from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.product import Product
from app.models.category import Category
from app.models.review import Review
from app.models.user import UserRole
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse
from app.auth.dependencies import require_role, get_current_user

router=APIRouter(prefix="/products", tags=["Products"])

def enrich(p):
    p.average_rating = float(p.reviews and sum(r.rating for r in p.reviews)/len(p.reviews) or 0)
    p.review_count = len(p.reviews)
    return p

@router.post("", response_model=ProductResponse, status_code=201)
def create(data:ProductCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    if db.scalar(select(Product).where(Product.sku==data.sku)): raise HTTPException(409,"SKU already exists")
    if not db.get(Category,data.category_id): raise HTTPException(404,"Category not found")
    p=Product(**data.model_dump()); db.add(p); db.commit(); db.refresh(p); return enrich(p)

@router.get("", response_model=list[ProductResponse])
def list_products(name:str|None=None,category_id:int|None=None,min_price:float|None=None,max_price:float|None=None,
                  in_stock:bool=False,sort_by:str="created_at",order:str="desc",skip:int=0,limit:int=10,
                  db:Session=Depends(get_db)):
    q=select(Product).where(Product.is_active==True)
    if name: q=q.where(Product.name.ilike(f"%{name}%"))
    if category_id: q=q.where(Product.category_id==category_id)
    if min_price is not None: q=q.where(Product.price>=min_price)
    if max_price is not None: q=q.where(Product.price<=max_price)
    if in_stock: q=q.where(Product.stock_quantity>0)
    col=Product.price if sort_by=="price" else Product.created_at
    q=q.order_by(col.asc() if order=="asc" else col.desc()).offset(skip).limit(limit)
    return [enrich(p) for p in db.scalars(q).all()]

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id:int,db:Session=Depends(get_db)):
    p=db.scalar(select(Product).where(Product.id==product_id,Product.is_active==True))
    if not p: raise HTTPException(404,"Product not found")
    return enrich(p)

@router.put("/{product_id}", response_model=ProductResponse)
def update(product_id:int,data:ProductUpdate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(p,k,v)
    db.commit(); db.refresh(p); return enrich(p)

@router.delete("/{product_id}")
def delete(product_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    p.is_active=False; db.commit(); return {"message":"Product soft deleted"}

@router.post("/{product_id}/reviews",response_model=ReviewResponse,status_code=201)
def add_review(product_id:int,data:ReviewCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    from app.models.order import Order,OrderItem,OrderStatus
    delivered=db.scalar(select(Order.id).join(OrderItem).where(Order.customer_id==user.id,Order.status==OrderStatus.Delivered,OrderItem.product_id==product_id))
    if not delivered: raise HTTPException(400,"You can review only products from your delivered orders")
    if db.scalar(select(Review).where(Review.product_id==product_id,Review.customer_id==user.id)):
        raise HTTPException(409,"You have already reviewed this product")
    r=Review(product_id=product_id,customer_id=user.id,**data.model_dump()); db.add(r); db.commit(); db.refresh(r); return r

@router.get("/{product_id}/reviews",response_model=list[ReviewResponse])
def reviews(product_id:int,skip:int=0,limit:int=10,db:Session=Depends(get_db)):
    return db.scalars(select(Review).where(Review.product_id==product_id).offset(skip).limit(limit)).all()
