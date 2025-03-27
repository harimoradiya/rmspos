from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RestaurantOutletBase(BaseModel):
    name: str
    address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "active"

class RestaurantOutletCreate(RestaurantOutletBase):
    chain_id: int

class RestaurantOutletUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None

class RestaurantOutletInDB(RestaurantOutletBase):
    id: int
    chain_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RestaurantOutletResponse(RestaurantOutletInDB):
    pass