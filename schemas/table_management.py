from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.table_management import TableStatus

class AreaBase(BaseModel):
    name: str
    description: Optional[str] = None
    outlet_id: int

class AreaCreate(AreaBase):
    pass

class AreaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class AreaResponse(AreaBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class TableBase(BaseModel):
    name: str
    capacity: int
    area_id: int

class TableCreate(TableBase):
    pass

class TableUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[TableStatus] = None
    is_active: Optional[bool] = None

class TableResponse(TableBase):
    id: int
    status: TableStatus
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True