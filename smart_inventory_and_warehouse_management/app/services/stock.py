from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Inventory, StockMovement, Product, Warehouse
from app.services.email import send_email

def get_or_create_locked(db:Session,product_id:int,warehouse_id:int):
    inv=db.execute(select(Inventory).where(Inventory.product_id==product_id,Inventory.warehouse_id==warehouse_id).with_for_update()).scalar_one_or_none()
    if not inv:
        wh=db.get(Warehouse,warehouse_id)
        if not wh or not wh.is_active: raise HTTPException(400,"Warehouse is inactive or missing")
        inv=Inventory(product_id=product_id,warehouse_id=warehouse_id,quantity_on_hand=0,quantity_reserved=0); db.add(inv); db.flush()
    return inv

def mutate_stock(db,user_id,product_id,warehouse_id,delta,movement_type,reference_id=None):
    inv=get_or_create_locked(db,product_id,warehouse_id)
    new=inv.quantity_on_hand+delta
    if new<0: raise HTTPException(409,"Stock cannot go below zero")
    if delta>0:
        cap=db.execute(select(func.coalesce(func.sum(Inventory.quantity_on_hand),0)).where(Inventory.warehouse_id==warehouse_id,Inventory.id!=inv.id).with_for_update()).scalar_one()
        wh=db.get(Warehouse,warehouse_id)
        if cap+new>wh.capacity: raise HTTPException(409,"Warehouse capacity exceeded")
    inv.quantity_on_hand=new
    db.add(StockMovement(product_id=product_id,warehouse_id=warehouse_id,movement_type=movement_type,quantity=delta,reference_id=reference_id,balance_after=new,performed_by=user_id))
    return inv

def reserve(db,user_id,product_id,warehouse_id,qty):
    inv=get_or_create_locked(db,product_id,warehouse_id)
    if inv.quantity_on_hand-inv.quantity_reserved<qty: raise HTTPException(409,"Insufficient available stock")
    inv.quantity_reserved+=qty
    return inv

def release(db,product_id,warehouse_id,qty):
    inv=get_or_create_locked(db,product_id,warehouse_id)
    if inv.quantity_reserved<qty: raise HTTPException(409,"Invalid reservation")
    inv.quantity_reserved-=qty
    return inv

def dispatch_reserved(db,user_id,product_id,warehouse_id,qty,reference_id):
    inv=get_or_create_locked(db,product_id,warehouse_id)
    if inv.quantity_reserved<qty or inv.quantity_on_hand<qty: raise HTTPException(409,"Invalid reserved stock")
    inv.quantity_reserved-=qty; inv.quantity_on_hand-=qty
    db.add(StockMovement(product_id=product_id,warehouse_id=warehouse_id,movement_type="Sale Dispatch",quantity=-qty,reference_id=reference_id,balance_after=inv.quantity_on_hand,performed_by=user_id))
    return inv


def schedule_low_stock_alert(db, background_tasks, product_id, warehouse_id):
    from app.models import User
    inv=get_or_create_locked(db,product_id,warehouse_id)
    if inv.quantity_on_hand-inv.quantity_reserved < inv.product.reorder_level:
        managers=db.scalars(select(User).where(User.role=="Inventory Manager",User.is_active==True)).all()
        body=(f"Low stock alert: {inv.product.name} ({inv.product.sku})\n"
              f"Warehouse: {warehouse_id}\nAvailable: {inv.quantity_on_hand-inv.quantity_reserved}\n"
              f"Reorder level: {inv.product.reorder_level}\nSuggested quantity: {inv.product.reorder_quantity}")
        for manager in managers:
            background_tasks.add_task(send_email,manager.email,"Low Stock Alert",body)
