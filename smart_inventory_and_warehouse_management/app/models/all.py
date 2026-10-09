from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, Numeric, Text, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class User(Base, TimestampMixin):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(100), unique=True, index=True)
    email: Mapped[str]=mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(30), default="Warehouse Staff")
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    warehouse_id: Mapped[int|None]=mapped_column(ForeignKey("warehouses.id"), nullable=True)

class Category(Base, TimestampMixin):
    __tablename__="categories"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(100), unique=True)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    products=relationship("Product", back_populates="category")

class Supplier(Base, TimestampMixin):
    __tablename__="suppliers"
    id: Mapped[int]=mapped_column(primary_key=True)
    supplier_code: Mapped[str]=mapped_column(String(50), unique=True)
    name: Mapped[str]=mapped_column(String(150))
    email: Mapped[str]=mapped_column(String(150), unique=True)
    phone: Mapped[str]=mapped_column(String(10))
    gst_number: Mapped[str]=mapped_column(String(15))
    address: Mapped[str]=mapped_column(Text)
    lead_time_days: Mapped[int]=mapped_column(Integer, default=0)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    products=relationship("Product", back_populates="preferred_supplier")
    purchase_orders=relationship("PurchaseOrder", back_populates="supplier")

class Warehouse(Base, TimestampMixin):
    __tablename__="warehouses"
    id: Mapped[int]=mapped_column(primary_key=True)
    warehouse_code: Mapped[str]=mapped_column(String(50), unique=True)
    name: Mapped[str]=mapped_column(String(150))
    city: Mapped[str]=mapped_column(String(100))
    address: Mapped[str]=mapped_column(Text)
    capacity: Mapped[int]=mapped_column(Integer)
    manager_id: Mapped[int|None]=mapped_column(ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    inventories=relationship("Inventory", back_populates="warehouse")

class Product(Base, TimestampMixin):
    __tablename__="products"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(150), index=True)
    sku: Mapped[str]=mapped_column(String(80), unique=True, index=True)
    barcode: Mapped[str|None]=mapped_column(String(80), unique=True, nullable=True)
    category_id: Mapped[int]=mapped_column(ForeignKey("categories.id"))
    unit: Mapped[str]=mapped_column(String(20))
    cost_price: Mapped[Decimal]=mapped_column(Numeric(12,2))
    selling_price: Mapped[Decimal]=mapped_column(Numeric(12,2))
    reorder_level: Mapped[int]=mapped_column(Integer)
    reorder_quantity: Mapped[int]=mapped_column(Integer)
    preferred_supplier_id: Mapped[int|None]=mapped_column(ForeignKey("suppliers.id"), nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    category=relationship("Category", back_populates="products")
    preferred_supplier=relationship("Supplier", back_populates="products")
    inventories=relationship("Inventory", back_populates="product")

class Inventory(Base, TimestampMixin):
    __tablename__="inventory"
    __table_args__=(UniqueConstraint("product_id","warehouse_id",name="uq_inventory_product_warehouse"),)
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    quantity_on_hand: Mapped[int]=mapped_column(Integer, default=0)
    quantity_reserved: Mapped[int]=mapped_column(Integer, default=0)
    product=relationship("Product", back_populates="inventories")
    warehouse=relationship("Warehouse", back_populates="inventories")

class StockMovement(Base, TimestampMixin):
    __tablename__="stock_movements"
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    movement_type: Mapped[str]=mapped_column(String(40))
    quantity: Mapped[int]=mapped_column(Integer)
    reference_id: Mapped[int|None]=mapped_column(Integer, nullable=True)
    balance_after: Mapped[int]=mapped_column(Integer)
    performed_by: Mapped[int]=mapped_column(ForeignKey("users.id"))

class PurchaseOrder(Base, TimestampMixin):
    __tablename__="purchase_orders"
    id: Mapped[int]=mapped_column(primary_key=True)
    po_number: Mapped[str]=mapped_column(String(60), unique=True, index=True)
    supplier_id: Mapped[int]=mapped_column(ForeignKey("suppliers.id"))
    warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    expected_delivery_date: Mapped[date]=mapped_column(Date)
    received_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    total_amount: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    status: Mapped[str]=mapped_column(String(30), default="Draft")
    supplier=relationship("Supplier", back_populates="purchase_orders")
    items=relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")

class PurchaseOrderItem(Base):
    __tablename__="purchase_order_items"
    id: Mapped[int]=mapped_column(primary_key=True)
    purchase_order_id: Mapped[int]=mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    quantity_ordered: Mapped[int]=mapped_column(Integer)
    quantity_received: Mapped[int]=mapped_column(Integer, default=0)
    unit_cost: Mapped[Decimal]=mapped_column(Numeric(12,2))
    purchase_order=relationship("PurchaseOrder", back_populates="items")

class Customer(Base, TimestampMixin):
    __tablename__="customers"
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_code: Mapped[str]=mapped_column(String(50), unique=True)
    name: Mapped[str]=mapped_column(String(150))
    email: Mapped[str]=mapped_column(String(150), unique=True)
    phone: Mapped[str]=mapped_column(String(10))
    address: Mapped[str]=mapped_column(Text)
    credit_limit: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    sales_orders=relationship("SalesOrder", back_populates="customer")

class SalesOrder(Base, TimestampMixin):
    __tablename__="sales_orders"
    id: Mapped[int]=mapped_column(primary_key=True)
    so_number: Mapped[str]=mapped_column(String(60), unique=True, index=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id"))
    warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    subtotal: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    tax_amount: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    grand_total: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    status: Mapped[str]=mapped_column(String(30), default="Draft")
    courier_name: Mapped[str|None]=mapped_column(String(100), nullable=True)
    tracking_number: Mapped[str|None]=mapped_column(String(100), unique=True, nullable=True)
    dispatched_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    customer=relationship("Customer", back_populates="sales_orders")
    items=relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")

class SalesOrderItem(Base):
    __tablename__="sales_order_items"
    id: Mapped[int]=mapped_column(primary_key=True)
    sales_order_id: Mapped[int]=mapped_column(ForeignKey("sales_orders.id"))
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]=mapped_column(Integer)
    unit_price: Mapped[Decimal]=mapped_column(Numeric(12,2))
    line_total: Mapped[Decimal]=mapped_column(Numeric(14,2))
    sales_order=relationship("SalesOrder", back_populates="items")

class Return(Base, TimestampMixin):
    __tablename__="returns"
    id: Mapped[int]=mapped_column(primary_key=True)
    so_id: Mapped[int]=mapped_column(ForeignKey("sales_orders.id"))
    reason: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(20), default="Requested")
    refund_amount: Mapped[Decimal]=mapped_column(Numeric(14,2), default=0)
    rejection_reason: Mapped[str|None]=mapped_column(Text, nullable=True)
    inspected_by: Mapped[int|None]=mapped_column(ForeignKey("users.id"), nullable=True)
    items=relationship("ReturnItem", back_populates="return_request", cascade="all, delete-orphan")

class ReturnItem(Base):
    __tablename__="return_items"
    id: Mapped[int]=mapped_column(primary_key=True)
    return_id: Mapped[int]=mapped_column(ForeignKey("returns.id"))
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]=mapped_column(Integer)
    condition: Mapped[str|None]=mapped_column(String(20), nullable=True)
    return_request=relationship("Return", back_populates="items")

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    action: Mapped[str]=mapped_column(String(30))
    entity_type: Mapped[str]=mapped_column(String(50))
    entity_id: Mapped[int]=mapped_column(Integer)
    old_value: Mapped[str|None]=mapped_column(Text, nullable=True)
    new_value: Mapped[str|None]=mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Transfer(Base, TimestampMixin):
    __tablename__="transfers"
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    source_warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    destination_warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int]=mapped_column(Integer)
    quantity_received: Mapped[int]=mapped_column(Integer, default=0)
    status: Mapped[str]=mapped_column(String(20), default="Pending")
    shortage: Mapped[int]=mapped_column(Integer, default=0)

class Adjustment(Base, TimestampMixin):
    __tablename__="adjustments"
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int]=mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int]=mapped_column(Integer)
    reason: Mapped[str]=mapped_column(String(30))
    status: Mapped[str]=mapped_column(String(20), default="Pending")
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int|None]=mapped_column(ForeignKey("users.id"), nullable=True)
