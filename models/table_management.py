from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from utils.database import Base
import enum

class TableStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    OUT_OF_SERVICE = "out_of_service"
    WAITING_FOR_CLEANING = "waiting_for_cleaning" # Table needs to be cleaned before the next use
    MERGED = "merged"                # Tables have been combined for a large group

class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    outlet_id = Column(Integer, ForeignKey("restaurant_outlets.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    outlet = relationship("RestaurantOutlet", back_populates="areas")
    tables = relationship("Table", back_populates="area", cascade="all, delete-orphan") 
class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    status = Column(Enum(TableStatus), default=TableStatus.AVAILABLE)
    area_id = Column(Integer, ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    area = relationship("Area", back_populates="tables")
    orders = relationship("Order", back_populates="table")