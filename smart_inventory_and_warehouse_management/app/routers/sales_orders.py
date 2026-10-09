from datetime import datetime,timedelta
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SalesOrder,SalesOrderItem,Customer,Product,Inventory
from app.schemas import SOCreate,SOOut,DispatchIn
from app.auth.dependencies import require_roles,get_current_user
from app.services.audit import audit
from app.services.stock import reserve,release,dispatch_reserved,schedule_low_stock_alert
from app.services.email import send_email
from app.services.access import warehouse_allowed
router=APIRouter(prefix="/sales-orders",tags=["Sales Orders"])
def next_so(db):return f"SO-{datetime.now():%Y%m%d}-{(db.query(SalesOrder).count()+1):04d}"
@router.post("",response_model=SOOut,status_code=201)
def create(d:SOCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    c=db.get(Customer,d.customer_id)
    if not c or not c.is_active:raise HTTPException(409,"Customer inactive or missing")
    subtotal=Decimal(0);x=SalesOrder(so_number=next_so(db),customer_id=c.id,warehouse_id=d.warehouse_id,status="Draft",created_by=u.id);db.add(x);db.flush()
    for i in d.items:
        p=db.get(Product,i.product_id)
        if not p or not p.is_active:raise HTTPException(409,f"Product {i.product_id} inactive or missing")
        line=p.selling_price*i.quantity;subtotal+=line;x.items.append(SalesOrderItem(product_id=p.id,quantity=i.quantity,unit_price=p.selling_price,line_total=line))
    x.subtotal=subtotal;x.tax_amount=(subtotal*Decimal("0.18"));x.grand_total=x.subtotal+x.tax_amount
    db.commit();db.refresh(x);audit(db,u.id,"create","SalesOrder",x.id,new={"so_number":x.so_number});db.commit();return x
@router.get("",response_model=list[SOOut])
def list_(status:str|None=None,warehouse_id:int|None=None,customer_id:int|None=None,skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    q=select(SalesOrder)
    if status:q=q.where(SalesOrder.status==status)
    if warehouse_id:q=q.where(SalesOrder.warehouse_id==warehouse_id)
    if customer_id:q=q.where(SalesOrder.customer_id==customer_id)
    return db.scalars(q.offset(skip).limit(limit)).all()
@router.get("/{so_id}",response_model=SOOut)
def get(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(SalesOrder,so_id)
    if not x:raise HTTPException(404,"Sales order not found")
    return x
@router.put("/{so_id}/confirm",response_model=SOOut)
def confirm(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.execute(select(SalesOrder).where(SalesOrder.id==so_id).with_for_update()).scalar_one_or_none()
    if not x:raise HTTPException(404,"Sales order not found")
    if x.status!="Draft":raise HTTPException(409,"Only Draft orders can be confirmed")
    open_total=db.scalar(select(func.coalesce(func.sum(SalesOrder.grand_total),0)).where(SalesOrder.customer_id==x.customer_id,SalesOrder.status.in_(["Confirmed","Picked","Packed","Dispatched"]),SalesOrder.id!=x.id))
    if open_total+x.grand_total> x.customer.credit_limit:raise HTTPException(409,"Customer credit limit exceeded")
    for i in x.items:reserve(db,u.id,i.product_id,x.warehouse_id,i.quantity)
    x.status="Confirmed";audit(db,u.id,"approve","SalesOrder",x.id);db.commit();db.refresh(x);return x
@router.put("/{so_id}/cancel",response_model=SOOut)
def cancel(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.execute(select(SalesOrder).where(SalesOrder.id==so_id).with_for_update()).scalar_one_or_none()
    if not x:raise HTTPException(404,"Sales order not found")
    if x.status in ["Dispatched","Delivered","Cancelled"]:raise HTTPException(409,"Order cannot be cancelled")
    if x.status in ["Confirmed","Picked","Packed"]:
        for i in x.items:release(db,i.product_id,x.warehouse_id,i.quantity)
    x.status="Cancelled";audit(db,u.id,"cancel","SalesOrder",x.id);db.commit();db.refresh(x);return x
@router.put("/{so_id}/pick",response_model=SOOut)
def pick(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Warehouse Staff"))):return transition(so_id,"Confirmed","Picked",db,u)
@router.put("/{so_id}/pack",response_model=SOOut)
def pack(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Warehouse Staff"))):return transition(so_id,"Picked","Packed",db,u)
@router.put("/{so_id}/dispatch",response_model=SOOut)
def dispatch(so_id:int,d:DispatchIn,background_tasks:BackgroundTasks,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Warehouse Staff"))):
    x=db.execute(select(SalesOrder).where(SalesOrder.id==so_id).with_for_update()).scalar_one_or_none()
    if not x:raise HTTPException(404,"Sales order not found")
    warehouse_allowed(u,x.warehouse_id)
    if x.status!="Packed":raise HTTPException(409,"Order must be Packed before dispatch")
    if db.scalar(select(SalesOrder).where(SalesOrder.tracking_number==d.tracking_number)):raise HTTPException(409,"Tracking number exists")
    for i in x.items:dispatch_reserved(db,u.id,i.product_id,x.warehouse_id,i.quantity,x.id);schedule_low_stock_alert(db,background_tasks,i.product_id,x.warehouse_id)
    x.status="Dispatched";x.courier_name=d.courier_name;x.tracking_number=d.tracking_number;x.dispatched_at=datetime.utcnow();audit(db,u.id,"update","SalesOrder",x.id,new={"status":"Dispatched"});db.commit();db.refresh(x)
    background_tasks.add_task(send_email,x.customer.email,"Sales Order Dispatched",f"Order {x.so_number} dispatched. Tracking: {x.tracking_number}");return x
@router.put("/{so_id}/deliver",response_model=SOOut)
def deliver(so_id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Warehouse Staff"))):
    x=db.get(SalesOrder,so_id)
    if not x:raise HTTPException(404,"Sales order not found")
    warehouse_allowed(u,x.warehouse_id)
    if x.status!="Dispatched":raise HTTPException(409,"Order must be Dispatched")
    x.status="Delivered";x.delivered_at=datetime.utcnow();db.commit();db.refresh(x);return x

def transition(so_id,from_status,to_status,db,u):
    x=db.get(SalesOrder,so_id)
    if not x:raise HTTPException(404,"Sales order not found")
    warehouse_allowed(u,x.warehouse_id)
    if x.status!=from_status:raise HTTPException(409,f"Order must be {from_status}")
    x.status=to_status;db.commit();db.refresh(x);return x
