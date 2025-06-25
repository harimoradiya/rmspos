from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Boolean, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class MenuScope(str, enum.Enum):
    CHAIN = "chain"
    OUTLET = "outlet"

class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scope = Column(Enum(MenuScope), nullable=False)
    chain_id = Column(Integer, ForeignKey("restaurant_chains.id", ondelete="CASCADE"), nullable=True)
    outlet_id = Column(Integer, ForeignKey("restaurant_outlets.id", ondelete="CASCADE"), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chain = relationship("RestaurantChain", back_populates="menu_categories")
    menu_items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")   
class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey("menu_categories.id", ondelete="CASCADE"), nullable=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("MenuCategory", back_populates="menu_items")