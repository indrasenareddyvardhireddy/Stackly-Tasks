from datetime import date,timedelta,datetime
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PurchaseOrder,PurchaseOrderItem,Supplier,Warehouse,Product
from app.schemas import POCreate,POOut,POReceive
from app.auth.dependencies import require_roles
from app.services.audit import audit
from app.services.stock import mutate_stock,schedule_low_stock_alert
from app.services.email import send_email
from app.services.access import warehouse_allowed
router=APIRouter(prefix="/purchase-orders",tags=["Purchase Orders"])
def next_po(db): return f"PO-{date.today():%Y%m%d}-{(db.query(PurchaseOrder).count()+1):04d}"
@router.post("",response_model=POOut,status_code=201)
def create(d:POCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    s=db.get(Supplier,d.supplier_id);w=db.get(Warehouse,d.warehouse_id)
    if not s or not s.is_active:raise HTTPException(409,"Supplier is inactive or missing")
    if not w or not w.is_active:raise HTTPException(409,"Warehouse is inactive or missing")
    expected=d.expected_delivery_date or (date.today()+timedelta(days=s.lead_time_days))
    x=PurchaseOrder(po_number=next_po(db),supplier_id=s.id,warehouse_id=w.id,expected_delivery_date=expected,status="Draft",created_by=u.id)
    db.add(x);db.flush(); total=Decimal(0)
    for i in d.items:
        if not db.get(Product,i.product_id):raise HTTPException(404,f"Product {i.product_id} not found")
        x.items.append(PurchaseOrderItem(product_id=i.product_id,quantity_ordered=i.quantity_ordered,unit_cost=i.unit_cost));total+=i.quantity_ordered*i.unit_cost
    x.total_amount=total;audit(db,u.id,"create","PurchaseOrder",x.id,new={"po_number":x.po_number});db.commit();db.refresh(x);return x
@router.get("",response_model=list[POOut])
def list_(status:str|None=None,warehouse_id:int|None=None,supplier_id:int|None=None,skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(PurchaseOrder)
    if status:q=q.where(PurchaseOrder.status==status)
    if warehouse_id:q=q.where(PurchaseOrder.warehouse_id==warehouse_id)
    if supplier_id:q=q.where(PurchaseOrder.supplier_id==supplier_id)
    return db.scalars(q.offset(skip).limit(limit)).all()
@router.get("/{po_id}",response_model=POOut)
def get(po_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(PurchaseOrder,po_id)
    if not x:raise HTTPException(404,"Purchase order not found")
    return x
@router.put("/{po_id}/approve",response_model=POOut)
def approve(po_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager")),background_tasks:BackgroundTasks=None):
    x=db.get(PurchaseOrder,po_id)
    if not x:raise HTTPException(404,"Purchase order not found")
    if x.status!="Draft":raise HTTPException(409,"Only Draft purchase orders can be approved")
    x.status="Approved";audit(db,u.id,"approve","PurchaseOrder",x.id);db.commit();db.refresh(x)
    if background_tasks:background_tasks.add_task(send_email,x.supplier.email,"Purchase Order Approved",f"Purchase order {x.po_number} has been approved.")
    return x
@router.post("/{po_id}/receive",response_model=POOut)
def receive(po_id:int,d:POReceive,background_tasks:BackgroundTasks,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(PurchaseOrder,po_id)
    if not x:raise HTTPException(404,"Purchase order not found")
    warehouse_allowed(u,x.warehouse_id)
    if x.status not in ["Approved","Partially Received"]:raise HTTPException(409,"Only Approved purchase orders can receive goods")
    for r in d.items:
        item=next((z for z in x.items if z.id==r.item_id),None)
        if not item:raise HTTPException(404,"PO item not found")
        if item.quantity_received+r.quantity>item.quantity_ordered:raise HTTPException(409,"Received quantity exceeds ordered quantity")
        item.quantity_received+=r.quantity;mutate_stock(db,u.id,item.product_id,x.warehouse_id,r.quantity,"Purchase Receipt",x.id);schedule_low_stock_alert(db,background_tasks,item.product_id,x.warehouse_id)
    x.status="Received" if all(i.quantity_received==i.quantity_ordered for i in x.items) else "Partially Received"
    if x.status=="Received":x.received_at=datetime.utcnow()
    db.commit();db.refresh(x);return x
@router.put("/{po_id}/cancel",response_model=POOut)
def cancel(po_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(PurchaseOrder,po_id)
    if not x:raise HTTPException(404,"Purchase order not found")
    if x.status not in ["Draft","Approved"] or any(i.quantity_received for i in x.items):raise HTTPException(409,"Purchase order cannot be cancelled")
    x.status="Cancelled";audit(db,u.id,"cancel","PurchaseOrder",x.id);db.commit();db.refresh(x);return x
