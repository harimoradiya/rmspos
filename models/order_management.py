from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from models.table_management import TableStatus
import enum

class OrderType(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class KOTStatus(str, enum.Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    token_number = Column(String, unique=True, index=True, nullable=False)
    outlet_id = Column(Integer, ForeignKey("restaurant_outlets.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    order_type = Column(String, nullable=False)
    status = Column(String, default=OrderStatus.PENDING.value)
    total_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    outlet = relationship("RestaurantOutlet", back_populates="orders")
    invoices = relationship("Invoice", back_populates="order", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.order_type == OrderType.DINE_IN.value and not self.table_id:
            raise ValueError("Table ID is required for dine-in orders")
        
    def update_table_status(self, db):
        if self.table_id:
            table = self.table
            if self.status in [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]:
                table.status = TableStatus.AVAILABLE
            elif self.order_type == OrderType.DINE_IN.value:
                table.status = TableStatus.OCCUPIED
            db.commit()
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")
    kot = relationship("KOT", back_populates="order_item", uselist=False)

class KOT(Base):
    __tablename__ = "kots"

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    status = Column(String, default=KOTStatus.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order_item = relationship("OrderItem", back_populates="kot")