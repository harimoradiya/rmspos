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
    updated_at = Column(DateTime(timezone=True ), onupdate=func.now())
    outlet_id = Column(Integer, ForeignKey("restaurant_outlets.id"), nullable=True)  # New field
    
    
    # Relationship with restaurants (for owners)
    restaurant_chains = relationship("RestaurantChain", back_populates="owner", cascade="all, delete-orphan")
    # Relationship with outlet (required for staff roles)
    outlet = relationship("RestaurantOutlet", back_populates="users")
    
    @property
    def requires_outlet(self) -> bool:
        """Check if the user role requires an outlet assignment."""
        return self.role in [UserRole.MANAGER.value, UserRole.WAITER.value, UserRole.KITCHEN.value]
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if the user's outlet has an active subscription."""
        return self.outlet and self.outlet.has_active_subscription()
    class Config:
        orm_mode = True