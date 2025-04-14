from sqlalchemy import Column, Integer,Boolean, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class RestaurantOutlet(Base):
    __tablename__ = "restaurant_outlets"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(Integer, ForeignKey("restaurant_chains.id"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_active = Column(Boolean, default=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chain = relationship("RestaurantChain", back_populates="outlets")
    menu_categories = relationship("MenuCategory", back_populates="outlet", cascade="all, delete-orphan")   
    areas = relationship("Area", back_populates="outlet", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="outlet", cascade="all, delete-orphan")
    users = relationship("User", back_populates="outlet", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="outlet", uselist=False)
    
    def has_active_subscription(self) -> bool:
        """Check if the outlet has an active subscription."""
        return self.subscription and self.subscription.is_active()
    class Config:
        orm_mode = True