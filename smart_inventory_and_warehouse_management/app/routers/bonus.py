from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Transfer,Adjustment
from app.auth.dependencies import require_roles
from app.services.stock import mutate_stock
from app.services.access import warehouse_allowed
router=APIRouter(tags=["Transfers & Adjustments"])
@router.post("/transfers",status_code=201)
def create_transfer(product_id:int,source_warehouse_id:int,destination_warehouse_id:int,quantity:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    warehouse_allowed(u,source_warehouse_id)
    if quantity<=0:raise HTTPException(422,"Quantity must be positive")
    x=Transfer(product_id=product_id,source_warehouse_id=source_warehouse_id,destination_warehouse_id=destination_warehouse_id,quantity=quantity,created_by=u.id);db.add(x);db.commit();db.refresh(x);return x
@router.get("/transfers")
def transfers(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):return db.scalars(select(Transfer).offset(skip).limit(limit)).all()
@router.put("/transfers/{id}/dispatch")
def transfer_dispatch(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(Transfer,id)
    if not x:raise HTTPException(404,"Transfer not found")
    warehouse_allowed(u,x.source_warehouse_id)
    if x.status!="Pending":raise HTTPException(409,"Invalid transfer status")
    mutate_stock(db,u.id,x.product_id,x.source_warehouse_id,-x.quantity,"Transfer Out",x.id);x.status="In Transit";db.commit();return x
@router.put("/transfers/{id}/receive")
def transfer_receive(id:int,quantity_received:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(Transfer,id)
    if not x:raise HTTPException(404,"Transfer not found")
    warehouse_allowed(u,x.destination_warehouse_id)
    if x.status!="In Transit" or quantity_received<0 or quantity_received>x.quantity:raise HTTPException(409,"Invalid received quantity/status")
    mutate_stock(db,u.id,x.product_id,x.destination_warehouse_id,quantity_received,"Transfer In",x.id);x.quantity_received=quantity_received;x.shortage=x.quantity-quantity_received;x.status="Received";db.commit();return x
@router.put("/transfers/{id}/cancel")
def transfer_cancel(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Transfer,id)
    if not x:raise HTTPException(404,"Transfer not found")
    if x.status!="Pending":raise HTTPException(409,"Only Pending transfer can be cancelled")
    x.status="Cancelled";db.commit();return x
@router.post("/adjustments",status_code=201)
def adjustment(product_id:int,warehouse_id:int,quantity:int,reason:str,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    warehouse_allowed(u,warehouse_id)
    if reason not in ["Damaged","Lost","Expired","Found","Count Correction"]:raise HTTPException(422,"Invalid adjustment reason")
    x=Adjustment(product_id=product_id,warehouse_id=warehouse_id,quantity=quantity,reason=reason,status="Pending",created_by=u.id);db.add(x);db.commit();db.refresh(x);return x
@router.get("/adjustments")
def adjustments(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):return db.scalars(select(Adjustment).offset(skip).limit(limit)).all()
@router.put("/adjustments/{id}/approve")
def approve_adjustment(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Adjustment,id)
    if not x or x.status!="Pending":raise HTTPException(409,"Invalid adjustment")
    mutate_stock(db,u.id,x.product_id,x.warehouse_id,x.quantity,"Adjustment",x.id);x.status="Approved";x.approved_by=u.id;db.commit();return x
@router.put("/adjustments/{id}/reject")
def reject_adjustment(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Adjustment,id)
    if not x or x.status!="Pending":raise HTTPException(409,"Invalid adjustment")
    x.status="Rejected";x.approved_by=u.id;db.commit();return x
