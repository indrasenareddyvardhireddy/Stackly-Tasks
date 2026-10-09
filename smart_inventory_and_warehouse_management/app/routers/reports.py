from datetime import date,timedelta,datetime
from fastapi import APIRouter,Depends
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product,Inventory,PurchaseOrder,SalesOrder,SalesOrderItem,Return,Warehouse,Supplier
from app.auth.dependencies import require_roles
router=APIRouter(prefix="/reports",tags=["Reports"])
@router.get("/dashboard")
def dashboard(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    total_products=db.scalar(select(func.count(Product.id)).where(Product.is_active==True));total_stock=db.scalar(select(func.coalesce(func.sum(Inventory.quantity_on_hand),0)))
    low=sum(1 for r in db.scalars(select(Inventory)).all() if r.quantity_on_hand-r.quantity_reserved<r.product.reorder_level)
    return {"total_products":total_products,"total_stock":total_stock,"low_stock_count":low,"pending_purchase_orders":db.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status.in_(["Draft","Approved","Partially Received"]))),"pending_sales_orders":db.scalar(select(func.count(SalesOrder.id)).where(SalesOrder.status.in_(["Confirmed","Picked","Packed","Dispatched"]))),"todays_dispatches":db.scalar(select(func.count(SalesOrder.id)).where(SalesOrder.dispatched_at>=datetime.combine(date.today(),datetime.min.time()))) }
@router.get("/stock-valuation")
def valuation(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    rows=db.execute(select(Warehouse.id,Warehouse.name,func.coalesce(func.sum(Inventory.quantity_on_hand*Product.cost_price),0)).join(Inventory,Inventory.warehouse_id==Warehouse.id).join(Product,Product.id==Inventory.product_id).group_by(Warehouse.id,Warehouse.name)).all()
    return [{"warehouse_id":r[0],"warehouse":r[1],"stock_value":r[2]} for r in rows]
@router.get("/low-stock")
def low_stock(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    return [{"product_id":r.product_id,"warehouse_id":r.warehouse_id,"available":r.quantity_on_hand-r.quantity_reserved,"reorder_level":r.product.reorder_level,"suggested_reorder_quantity":r.product.reorder_quantity,"preferred_supplier_id":r.product.preferred_supplier_id} for r in db.scalars(select(Inventory)).all() if r.quantity_on_hand-r.quantity_reserved<r.product.reorder_level]
@router.get("/sales")
def sales(start_date:date,end_date:date,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    a=datetime.combine(start_date,datetime.min.time());b=datetime.combine(end_date,datetime.max.time()); orders=db.scalars(select(SalesOrder).where(SalesOrder.created_at.between(a,b),SalesOrder.status!="Cancelled")).all();returns=db.scalars(select(Return).where(Return.created_at.between(a,b),Return.status=="Refunded")).all();return {"sales_count":len(orders),"revenue":sum(o.grand_total for o in orders),"returns":sum(r.refund_amount for r in returns)}
@router.get("/top-products")
def top_products(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    rows=db.execute(select(Product.id,Product.name,func.sum(SalesOrderItem.quantity).label("qty")).join(SalesOrderItem,SalesOrderItem.product_id==Product.id).join(SalesOrder,SalesOrder.id==SalesOrderItem.sales_order_id).where(SalesOrder.status.in_(["Dispatched","Delivered"])).group_by(Product.id,Product.name).order_by(func.sum(SalesOrderItem.quantity).desc()).limit(10)).all();return [{"product_id":r[0],"product":r[1],"quantity_sold":r[2]} for r in rows]
@router.get("/dead-stock")
def dead_stock(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    cutoff=datetime.utcnow()-timedelta(days=90);return [{"product_id":p.id,"name":p.name} for p in db.scalars(select(Product).where(Product.is_active==True)).all() if not db.scalar(select(SalesOrderItem.id).join(SalesOrder,SalesOrder.id==SalesOrderItem.sales_order_id).where(SalesOrderItem.product_id==p.id,SalesOrder.created_at>=cutoff,SalesOrder.status.in_(["Dispatched","Delivered"])).limit(1))]
@router.get("/supplier-performance")
def supplier_perf(db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    out=[]
    for s in db.scalars(select(Supplier)).all():
        pos=db.scalars(select(PurchaseOrder).where(PurchaseOrder.supplier_id==s.id,PurchaseOrder.status=="Received")).all();on=sum(1 for p in pos if p.received_at and p.received_at.date()<=p.expected_delivery_date);out.append({"supplier_id":s.id,"supplier":s.name,"on_time_percentage":(on/len(pos)*100 if pos else 0)})
    return out
