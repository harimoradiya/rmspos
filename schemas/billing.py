from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from models.billing import PaymentMethod, PaymentStatus

class PaymentCreate(BaseModel):
    amount: float
    method: PaymentMethod

class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class InvoiceCreate(BaseModel):
    order_id: int
    discount: Optional[float] = 0.0
    tax: Optional[float] = 0.0
    payments: List[PaymentCreate]

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    order_id: int
    subtotal: float
    discount: float
    tax: float
    total_amount: float
    created_at: datetime
    updated_at: datetime
    payments: List[PaymentResponse]

    class Config:
        orm_mode = True

class SplitItemRequest(BaseModel):
    item_ids: List[int]

class SplitBillRequest(BaseModel):
    order_id: int
    split_by: str = Field(..., description="'items' or 'amount'")
    splits: List[SplitItemRequest]

class SplitBillResponse(BaseModel):
    id: int
    invoice_id: int
    split_type: str
    split_data: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True