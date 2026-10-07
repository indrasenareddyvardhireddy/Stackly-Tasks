from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class PaymentMethod(str, enum.Enum):
    UPI="UPI"; Card="Card"; NetBanking="Net Banking"; COD="COD"
class PaymentResult(str, enum.Enum):
    Success="Success"; Failed="Failed"

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[PaymentResult] = mapped_column(Enum(PaymentResult), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order = relationship("Order", back_populates="payments")
