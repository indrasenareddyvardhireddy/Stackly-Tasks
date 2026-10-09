from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Warehouse,Inventory
from app.schemas import WarehouseCreate,WarehouseOut
from app.auth.dependencies import require_roles
from app.services.audit import audit
router=APIRouter(tags=["Warehouses"])
@router.post("/warehouses",response_model=WarehouseOut,status_code=201)
def create(d:WarehouseCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin"))):
    if db.scalar(select(Warehouse).where(Warehouse.warehouse_code==d.warehouse_code)): raise HTTPException(409,"Warehouse code exists")
    x=Warehouse(**d.model_dump(),created_by=u.id); db.add(x); db.flush(); audit(db,u.id,"create","Warehouse",x.id,new=d.model_dump()); db.commit(); db.refresh(x); return x
@router.get("/warehouses",response_model=list[WarehouseOut])
def list_(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))): return db.scalars(select(Warehouse).offset(skip).limit(limit)).all()
@router.get("/warehouses/{warehouse_id}",response_model=WarehouseOut)
def get(warehouse_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(Warehouse,warehouse_id)
    if not x: raise HTTPException(404,"Warehouse not found")
    return x
@router.put("/warehouses/{warehouse_id}",response_model=WarehouseOut)
def update(warehouse_id:int,d:WarehouseCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin"))):
    x=db.get(Warehouse,warehouse_id)
    if not x: raise HTTPException(404,"Warehouse not found")
    stock=db.scalar(select(func.coalesce(func.sum(Inventory.quantity_on_hand),0)).where(Inventory.warehouse_id==x.id))
    if stock>0 and (not d.is_active): raise HTTPException(409,"Warehouse with stock cannot be deactivated")
    for k,v in d.model_dump().items(): setattr(x,k,v)
    audit(db,u.id,"update","Warehouse",x.id); db.commit(); db.refresh(x); return x
@router.delete("/warehouses/{warehouse_id}",status_code=204)
def delete(warehouse_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin"))):
    x=db.get(Warehouse,warehouse_id)
    if not x: raise HTTPException(404,"Warehouse not found")
    stock=db.scalar(select(func.coalesce(func.sum(Inventory.quantity_on_hand),0)).where(Inventory.warehouse_id==x.id))
    if stock>0: raise HTTPException(409,"Warehouse with stock cannot be deleted")
    x.is_active=False; audit(db,u.id,"delete","Warehouse",x.id); db.commit()
@router.get("/warehouses/{warehouse_id}/inventory")
def inventory(warehouse_id:int,skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    return db.execute(select(Inventory).where(Inventory.warehouse_id==warehouse_id).offset(skip).limit(limit)).scalars().all()
