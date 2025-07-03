from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from utils.database import Base

class RestaurantChain(Base):
    __tablename__ = "restaurant_chains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    logo_url = Column(String, nullable=True)  # Store the URL of the uploaded logo
    status = Column(String, server_default='active')
    chain_type = Column(String, server_default='standard')  # Types could be: standard, franchise, corporate, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="restaurant_chains")
    outlets = relationship("RestaurantOutlet", back_populates="chain", cascade="all, delete-orphan")
    menu_categories = relationship("MenuCategory", back_populates="chain", cascade="all, delete-orphan")

    class Config:
        orm_mode = True