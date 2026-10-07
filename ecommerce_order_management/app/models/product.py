from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category = relationship("Category", back_populates="products")
    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    wishlist_items = relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")
