from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.menu_management import MenuScope

class MenuCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    scope: MenuScope
    chain_id: Optional[int] = None
    outlet_id: Optional[int] = None

class MenuCategoryCreate(MenuCategoryBase):
    pass

class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class MenuCategoryResponse(MenuCategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category_id: int

class MenuItemCreate(MenuItemBase):
    pass

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None

class MenuItemResponse(MenuItemBase):
    id: int
    is_available: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True