from datetime import datetime
from fastapi import APIRouter,Depends
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import require_role
from app.models.user import UserRole
from app.models.order import Order,OrderStatus,PaymentStatus,OrderItem
from app.models.product import Product
router=APIRouter(prefix="/reports",tags=["Reports"])

@router.get("/sales")
def sales(start_date:datetime,end_date:datetime,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    orders=db.scalars(select(Order).where(Order.created_at>=start_date,Order.created_at<=end_date)).all()
    paid=sum(o.grand_total for o in orders if o.payment_status==PaymentStatus.Paid)
    refunds=sum(o.grand_total for o in orders if o.payment_status==PaymentStatus.Refunded)
    return {"total_orders":len(orders),"total_revenue":paid,"total_refunds":refunds}

@router.get("/orders-by-status")
def by_status(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    rows=db.execute(select(Order.status,func.count(Order.id)).group_by(Order.status)).all()
    return {s.value:c for s,c in rows}

@router.get("/top-products")
def top_products(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    rows=db.execute(select(OrderItem.product_id,Product.name,func.sum(OrderItem.quantity).label("quantity"))
                   .join(Product).group_by(OrderItem.product_id,Product.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5)).all()
    return [{"product_id":r[0],"name":r[1],"quantity_sold":int(r[2])} for r in rows]

@router.get("/low-stock")
def low_stock(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Admin))):
    rows=db.scalars(select(Product).where(Product.is_active==True,Product.stock_quantity<5)).all()
    return [{"id":p.id,"name":p.name,"sku":p.sku,"stock_quantity":p.stock_quantity} for p in rows]
