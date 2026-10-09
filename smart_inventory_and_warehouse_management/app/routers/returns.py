from datetime import datetime,timedelta
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Return,ReturnItem,SalesOrder,SalesOrderItem
from app.schemas import ReturnCreate,ReturnInspect,ReturnDecision
from app.auth.dependencies import require_roles
from app.services.stock import mutate_stock
from app.services.email import send_email
from app.services.access import warehouse_allowed
router=APIRouter(tags=["Returns"])
@router.post("/sales-orders/{so_id}/returns",status_code=201)
def create(so_id:int,d:ReturnCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    so=db.get(SalesOrder,so_id)
    if not so or so.status!="Delivered" or not so.delivered_at:raise HTTPException(409,"Returns are allowed only for delivered orders")
    if datetime.utcnow()>so.delivered_at+timedelta(days=7):raise HTTPException(409,"Return window expired")
    x=Return(so_id=so.id,reason=d.reason,status="Requested",created_by=u.id);db.add(x);db.flush()
    for i in d.items:
        ordered=next((z.quantity for z in so.items if z.product_id==i.product_id),0)
        if i.quantity>ordered:raise HTTPException(409,"Return quantity exceeds delivered quantity")
        x.items.append(ReturnItem(product_id=i.product_id,quantity=i.quantity))
    db.commit();db.refresh(x);return {"id":x.id,"status":x.status}
@router.get("/returns")
def list_(status:str|None=None,skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(Return)
    if status:q=q.where(Return.status==status)
    return db.scalars(q.offset(skip).limit(limit)).all()
@router.put("/returns/{return_id}/inspect")
def inspect(return_id:int,d:ReturnInspect,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Warehouse Staff"))):
    x=db.get(Return,return_id)
    if not x:raise HTTPException(404,"Return not found")
    so=db.get(SalesOrder,x.so_id);warehouse_allowed(u,so.warehouse_id)
    if x.status!="Requested":raise HTTPException(409,"Return must be Requested")
    for item in d.items:
        ri=next((z for z in x.items if z.id==item.item_id),None)
        if not ri or item.condition not in ["Good","Damaged"]:raise HTTPException(422,"Invalid return item or condition")
        ri.condition=item.condition
    if any(i.condition is None for i in x.items):raise HTTPException(422,"Inspect every return item")
    x.status="Inspected";x.inspected_by=u.id;db.commit();return {"id":x.id,"status":x.status}
@router.put("/returns/{return_id}/approve")
def approve(return_id:int,background_tasks:BackgroundTasks,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.execute(select(Return).where(Return.id==return_id).with_for_update()).scalar_one_or_none()
    if not x:raise HTTPException(404,"Return not found")
    if x.status!="Inspected":raise HTTPException(409,"Only Inspected returns can be approved")
    so=db.get(SalesOrder,x.so_id);refund=Decimal(0)
    for ri in x.items:
        oi=next(z for z in so.items if z.product_id==ri.product_id);refund += oi.unit_price*ri.quantity*Decimal("1.18")
        if ri.condition=="Good":mutate_stock(db,u.id,ri.product_id,so.warehouse_id,ri.quantity,"Customer Return",x.id)
    x.refund_amount=refund;x.status="Refunded";db.commit();background_tasks.add_task(send_email,so.customer.email,"Return Approved",f"Refund of {refund} processed for order {so.so_number}.");return {"id":x.id,"status":x.status,"refund_amount":refund}
@router.put("/returns/{return_id}/reject")
def reject(return_id:int,d:ReturnDecision,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Return,return_id)
    if not x:raise HTTPException(404,"Return not found")
    if x.status!="Inspected":raise HTTPException(409,"Only Inspected returns can be rejected")
    if not d.rejection_reason:raise HTTPException(422,"Rejection reason is required")
    x.status="Rejected";x.rejection_reason=d.rejection_reason;db.commit();return {"id":x.id,"status":x.status}
