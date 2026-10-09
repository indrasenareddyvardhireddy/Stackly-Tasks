from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Inventory,StockMovement,Product
from app.auth.dependencies import require_roles
router=APIRouter(tags=["Inventory"])
@router.get("/inventory")
def inventory(product_id:int|None=None,warehouse_id:int|None=None,low_stock:bool=False,skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(Inventory)
    if product_id:q=q.where(Inventory.product_id==product_id)
    if warehouse_id:q=q.where(Inventory.warehouse_id==warehouse_id)
    rows=db.scalars(q.offset(skip).limit(limit)).all()
    if low_stock: rows=[r for r in rows if r.quantity_on_hand-r.quantity_reserved < r.product.reorder_level]
    return [{"product_id":r.product_id,"warehouse_id":r.warehouse_id,"quantity_on_hand":r.quantity_on_hand,"quantity_reserved":r.quantity_reserved,"quantity_available":r.quantity_on_hand-r.quantity_reserved} for r in rows]
@router.get("/inventory/{product_id}/{warehouse_id}")
def one(product_id:int,warehouse_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    r=db.scalar(select(Inventory).where(Inventory.product_id==product_id,Inventory.warehouse_id==warehouse_id))
    if not r:return {"product_id":product_id,"warehouse_id":warehouse_id,"quantity_on_hand":0,"quantity_reserved":0,"quantity_available":0}
    return {"product_id":r.product_id,"warehouse_id":r.warehouse_id,"quantity_on_hand":r.quantity_on_hand,"quantity_reserved":r.quantity_reserved,"quantity_available":r.quantity_on_hand-r.quantity_reserved}
@router.get("/stock-movements")
def movements(product_id:int|None=None,warehouse_id:int|None=None,movement_type:str|None=None,skip:int=0,limit:int=100,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(StockMovement)
    if product_id:q=q.where(StockMovement.product_id==product_id)
    if warehouse_id:q=q.where(StockMovement.warehouse_id==warehouse_id)
    if movement_type:q=q.where(StockMovement.movement_type==movement_type)
    return db.scalars(q.order_by(StockMovement.id.desc()).offset(skip).limit(limit)).all()
