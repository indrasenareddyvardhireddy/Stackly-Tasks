from datetime import datetime,timedelta
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import UserRole
from app.models.order import Order,OrderStatus,PaymentStatus
from app.models.return_request import ReturnRequest,ReturnStatus
from app.models.product import Product
from app.schemas.return_request import ReturnCreate,ReturnResponse,ReturnReject
from app.auth.dependencies import require_role
from app.utils.email import send_email
router=APIRouter(prefix="/returns",tags=["Returns"])

@router.post("/orders/{order_id}",response_model=ReturnResponse,status_code=201)
def request_return(order_id:int,data:ReturnCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    order=db.scalar(select(Order).where(Order.id==order_id,Order.customer_id==user.id))
    if not order: raise HTTPException(404,"Order not found")
    if order.status!=OrderStatus.Delivered or not order.delivered_at or datetime.utcnow()-order.delivered_at>timedelta(days=7):
        raise HTTPException(400,"Return allowed only within 7 days of delivery")
    if db.scalar(select(ReturnRequest).where(ReturnRequest.order_id==order_id)): raise HTTPException(409,"Return already requested")
    r=ReturnRequest(order_id=order_id,reason=data.reason); db.add(r); db.commit(); db.refresh(r); return r

@router.get("",response_model=list[ReturnResponse])
def list_returns(skip:int=0,limit:int=10,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin,UserRole.Customer))):
    q=select(ReturnRequest).join(Order)
    if user.role==UserRole.Customer: q=q.where(Order.customer_id==user.id)
    return db.scalars(q.offset(skip).limit(limit)).all()

@router.put("/{return_id}/approve",response_model=ReturnResponse)
def approve(return_id:int,background_tasks:BackgroundTasks,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    r=db.scalar(select(ReturnRequest).where(ReturnRequest.id==return_id))
    if not r: raise HTTPException(404,"Return not found")
    if r.status!=ReturnStatus.Requested: raise HTTPException(400,"Return is already processed")
    try:
        for item in r.order.items:
            p=db.get(Product,item.product_id); p.stock_quantity+=item.quantity
        r.status=ReturnStatus.Refunded; r.refund_amount=r.order.grand_total; r.order.payment_status=PaymentStatus.Refunded
        db.commit(); db.refresh(r)
        background_tasks.add_task(send_email,r.order.customer.email,"Return approved - refund processed",f"Return for {r.order.order_number} approved. Refund: ₹{r.refund_amount}")
        return r
    except Exception:
        db.rollback(); raise

@router.put("/{return_id}/reject",response_model=ReturnResponse)
def reject(return_id:int,data:ReturnReject,background_tasks:BackgroundTasks,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    r=db.get(ReturnRequest,return_id)
    if not r: raise HTTPException(404,"Return not found")
    r.status=ReturnStatus.Rejected; r.rejection_reason=data.rejection_reason
    db.commit(); db.refresh(r)
    background_tasks.add_task(send_email,r.order.customer.email,"Return rejected",f"Return for {r.order.order_number} was rejected: {r.rejection_reason}")
    return r
