from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from models.billing import PaymentMethod, PaymentStatus, InvoiceStatus
from models.order_management import OrderType

class PaymentCreate(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Payment amount, must be positive")
    method: PaymentMethod = Field(..., description="Payment method: cash, card, or upi")

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
        from_attributes = True

class InvoiceCreate(BaseModel):
    order_id: int = Field(..., gt=0, description="ID of the order to invoice")
    discount: float | None = Field(default=0.0, ge=0, description="Discount amount, must be non-negative")
    tax: float | None = Field(default=0.0, ge=0, description="Tax amount, must be non-negative")
    payments: List[PaymentCreate] = Field(..., min_items=1, description="List of payments, at least one required")


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    order_id: int
    subtotal: float
    discount: float
    tax: float
    total_amount: float
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    payments: List[PaymentResponse]
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True

class SplitItemRequest(BaseModel):
    item_ids: List[int] = Field(..., min_items=1, description="List of order item IDs for this split")
    amount: Optional[float] = Field(None, gt=0, description="Split amount for amount-based splits")

    @validator('item_ids')
    def validate_item_ids(cls, v, values, **kwargs):
        if values.get('amount') is None and not v:
            raise ValueError("Item IDs are required for item-based splits")
        return v

    @validator('amount')
    def validate_amount(cls, v, values, **kwargs):
        if values.get('split_by') == 'amount' and v is None:
            raise ValueError("Amount is required for amount-based splits")
        return v

class SplitBillRequest(BaseModel):
    order_id: int = Field(..., gt=0, description="ID of the order to split")
    split_by: str = Field(..., description="Split type: 'items' or 'amount'")
    discount: Optional[float] = Field(0.0, ge=0, description="Total discount to distribute across splits")
    tax: Optional[float] = Field(0.0, ge=0, description="Total tax to distribute across splits")
    splits: List[SplitItemRequest] = Field(..., min_items=1, description="List of splits")

    @validator('split_by')
    def validate_split_by(cls, v):
        if v not in ['items', 'amount']:
            raise ValueError("Split type must be 'items' or 'amount'")
        return v

    @validator('splits')
    def validate_splits(cls, v, values):
        if values.get('split_by') == 'items' and any(split.amount for split in v):
            raise ValueError("Amount should not be provided for item-based splits")
        if values.get('split_by') == 'amount' and any(split.item_ids for split in v):
            raise ValueError("Item IDs should not be provided for amount-based splits")
        return v

class SplitBillResponse(BaseModel):
    id: int
    invoice_id: int
    split_type: str
    split_data: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True