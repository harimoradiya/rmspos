from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from models.subscription import SubscriptionTier, SubscriptionStatus

class SubscriptionBase(BaseModel):
    tier: SubscriptionTier
    status: SubscriptionStatus

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(SubscriptionBase):
    pass

class SubscriptionResponse(SubscriptionBase):
    id: int
    user_id: int
    start_date: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True