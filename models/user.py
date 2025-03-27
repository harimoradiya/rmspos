from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # Owner of the RMS POS software
    OWNER = "owner"             # Owner of a specific restaurant/chain
    MANAGER = "manager"         # Staff: Manages operations at an outlet
    WAITER = "waiter"           # Staff: Takes orders
    KITCHEN = "kitchen"         # Staff: Handles KOT and food prep

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)  # Username for login
    hashed_password = Column(String, nullable=False)
    pin = Column(String(6), unique=True, index=True, nullable=True)  # 6-digit PIN for alternative login
    role = Column(Enum(UserRole, name="userrole", create_type=False), nullable=False)  # Keep enum lowercase
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship with restaurants (for owners)
    restaurant_chains = relationship("RestaurantChain", back_populates="owner")

    # Relationship with subscription
    subscription = relationship("models.subscription.Subscription", back_populates="user", uselist=False)

    class Config:
        orm_mode = True