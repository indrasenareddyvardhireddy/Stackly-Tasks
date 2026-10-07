from fastapi import APIRouter,Depends,BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.payment import Payment
from app.models.user import UserRole
from app.schemas.payment import PaymentCreate,PaymentResponse
from app.services.payment_service import pay
from app.models.order import Order
from app.auth.dependencies import require_role
from app.utils.email import send_email
router=APIRouter(prefix="/orders",tags=["Payments"])

@router.post("/{order_id}/pay",response_model=PaymentResponse)
def payment(order_id:int,data:PaymentCreate,background_tasks:BackgroundTasks,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    p=pay(db,user,order_id,data)
    if p.status.value=="Success": background_tasks.add_task(send_email,user.email,"Payment successful",f"Payment successful for order {p.order.order_number}.")
    return p

@router.get("/{order_id}/payments",response_model=list[PaymentResponse])
def payments(order_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin,UserRole.Customer))):
    order=db.get(Order,order_id)
    if not order or (user.role==UserRole.Customer and order.customer_id!=user.id): from fastapi import HTTPException; raise HTTPException(404,"Order not found")
    return db.scalars(select(Payment).where(Payment.order_id==order_id)).all()
