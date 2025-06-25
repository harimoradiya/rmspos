from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from models.subscription import SubscriptionTier, SubscriptionStatus
from fastapi import HTTPException 

class SubscriptionBase(BaseModel):
    tier: SubscriptionTier
    status: Optional[SubscriptionStatus] = SubscriptionStatus.ACTIVE


class SubscriptionCreate(SubscriptionBase):
    outlet_id: int
    duration_months: Optional[int] = 12  # Default to 1 year

class SubscriptionUpdate(BaseModel):
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None
    end_date: Optional[datetime] = None
    
    @validator('end_date')
    def validate_end_date(cls, v):
        if v and v < datetime.now():
            raise ValueError('End date cannot be in the past')
        return 

class SubscriptionResponse(SubscriptionBase):
    id: int
    outlet_id: int
    start_date: datetime
    end_date: Optional[datetime]
    # created_at: datetime
    # updated_at: Optional[datetime]
    # is_active: bool

    class Config:
        orm_mode = True