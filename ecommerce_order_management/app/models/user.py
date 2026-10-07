from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    Admin = "Admin"
    Customer = "Customer"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.Customer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cart = relationship("Cart", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    addresses = relationship("Address", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    reviews = relationship("Review", back_populates="customer", cascade="all, delete-orphan")
