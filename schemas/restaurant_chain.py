from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .restaurant_outlet import RestaurantOutletResponse

class RestaurantChainBase(BaseModel):
    name: str
    status: Optional[str] = "active"

class RestaurantChainCreate(RestaurantChainBase):
    pass

class RestaurantChainUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class RestaurantChainInDB(RestaurantChainBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RestaurantChainResponse(RestaurantChainInDB):
    outlets: Optional[List[RestaurantOutletResponse]] = None

class RestaurantChainCreate(BaseModel):
    name: str
    status: Optional[str] = None

class RestaurantChainDetailResponse(RestaurantChainResponse):
    restaurants: List[RestaurantOutletResponse]  