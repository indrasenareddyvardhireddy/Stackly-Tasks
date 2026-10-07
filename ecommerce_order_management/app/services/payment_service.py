from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.payment import Payment, PaymentMethod, PaymentResult
from app.models.user import User

def pay(db: Session, user: User, order_id: int, data):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == user.id))
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == OrderStatus.Cancelled:
        raise HTTPException(400, "Cancelled orders cannot be paid")
    if order.payment_status == PaymentStatus.Paid:
        raise HTTPException(409, "Order is already paid")
    if data.amount != order.grand_total:
        raise HTTPException(400, "Payment amount must match order grand total")
    if db.scalar(select(Payment).where(Payment.transaction_id == data.transaction_id)):
        raise HTTPException(409, "Transaction ID already exists")

    payment = Payment(order_id=order.id, amount=data.amount, payment_method=data.payment_method,
                      transaction_id=data.transaction_id, status=data.status)
    db.add(payment)
    if data.payment_method == PaymentMethod.COD:
        order.status = OrderStatus.Confirmed
        order.payment_status = PaymentStatus.Unpaid
    elif data.status == PaymentResult.Success:
        order.status = OrderStatus.Confirmed
        order.payment_status = PaymentStatus.Paid
    db.commit()
    db.refresh(payment)
    return payment
