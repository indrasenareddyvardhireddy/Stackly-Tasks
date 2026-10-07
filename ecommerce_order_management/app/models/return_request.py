from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class ReturnStatus(str, enum.Enum):
    Requested="Requested"; Approved="Approved"; Rejected="Rejected"; Refunded="Refunded"

class ReturnRequest(Base):
    __tablename__ = "return_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReturnStatus] = mapped_column(Enum(ReturnStatus), default=ReturnStatus.Requested)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12,2))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order = relationship("Order", back_populates="return_request")
