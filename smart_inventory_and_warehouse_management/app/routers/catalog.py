from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category,Product,Inventory
from app.schemas import CategoryCreate,CategoryOut,ProductCreate,ProductOut
from app.auth.dependencies import require_roles
from app.services.audit import audit
router=APIRouter(tags=["Catalog"])

@router.post("/categories",response_model=CategoryOut,status_code=201)
def create_category(d:CategoryCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    if db.scalar(select(Category).where(Category.name==d.name)): raise HTTPException(409,"Category exists")
    x=Category(name=d.name,created_by=u.id); db.add(x); db.flush(); audit(db,u.id,"create","Category",x.id,new=d.model_dump()); db.commit(); db.refresh(x); return x
@router.get("/categories",response_model=list[CategoryOut])
def categories(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))): return db.scalars(select(Category).offset(skip).limit(limit)).all()
@router.put("/categories/{category_id}",response_model=CategoryOut)
def update_category(category_id:int,d:CategoryCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Category,category_id)
    if not x: raise HTTPException(404,"Category not found")
    old={"name":x.name}; x.name=d.name; audit(db,u.id,"update","Category",x.id,old,d.model_dump()); db.commit(); db.refresh(x); return x
@router.delete("/categories/{category_id}",status_code=204)
def delete_category(category_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Category,category_id)
    if not x: raise HTTPException(404,"Category not found")
    if db.scalar(select(func.count(Product.id)).where(Product.category_id==x.id,Product.is_active==True)): raise HTTPException(409,"Category has active products")
    x.is_active=False; audit(db,u.id,"delete","Category",x.id,old={"is_active":True},new={"is_active":False}); db.commit()

@router.post("/products",response_model=ProductOut,status_code=201)
def create_product(d:ProductCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    if db.scalar(select(Product).where((Product.sku==d.sku)|(Product.barcode==d.barcode if d.barcode else False))): raise HTTPException(409,"SKU or barcode already exists")
    if not db.get(Category,d.category_id): raise HTTPException(404,"Category not found")
    x=Product(**d.model_dump(),created_by=u.id); db.add(x); db.flush(); audit(db,u.id,"create","Product",x.id,new=d.model_dump()); db.commit(); db.refresh(x); return x
@router.get("/products",response_model=list[ProductOut])
def products(skip:int=0,limit:int=50,search:str|None=None,category_id:int|None=None,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(Product)
    if search:q=q.where((Product.name.like(f"%{search}%"))|(Product.sku.like(f"%{search}%")))
    if category_id:q=q.where(Product.category_id==category_id)
    return db.scalars(q.offset(skip).limit(limit)).all()
@router.get("/products/{product_id}")
def product_detail(product_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    inv=db.scalars(select(Inventory).where(Inventory.product_id==p.id)).all()
    return {"product":ProductOut.model_validate(p),"warehouses":[{"warehouse_id":i.warehouse_id,"quantity_on_hand":i.quantity_on_hand,"quantity_reserved":i.quantity_reserved,"quantity_available":i.quantity_on_hand-i.quantity_reserved} for i in inv],"total_stock":sum(i.quantity_on_hand for i in inv)}
@router.put("/products/{product_id}",response_model=ProductOut)
def update_product(product_id:int,d:ProductCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Product,product_id)
    if not x: raise HTTPException(404,"Product not found")
    for k,v in d.model_dump().items(): setattr(x,k,v)
    audit(db,u.id,"update","Product",x.id); db.commit(); db.refresh(x); return x
@router.delete("/products/{product_id}",status_code=204)
def delete_product(product_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Product,product_id)
    if not x: raise HTTPException(404,"Product not found")
    stock=db.scalar(select(func.coalesce(func.sum(Inventory.quantity_on_hand),0)).where(Inventory.product_id==x.id))
    if stock>0: raise HTTPException(409,"Product with stock cannot be deactivated")
    x.is_active=False; audit(db,u.id,"delete","Product",x.id,old={"is_active":True},new={"is_active":False}); db.commit()
