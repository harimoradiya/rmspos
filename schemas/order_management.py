from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

import logging
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


# Configure logger
logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"

class OrderStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class KOTStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"



class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    menu_item_id: int
    quantity: int
    price: float
    notes: Optional[str] = None

    class Config:
        from_attributes = True

import logging
from typing import List, Optional
from pydantic import BaseModel, Field, validator


# Configure logger
logger = logging.getLogger(__name__)


# Enhanced Pydantic schemas
class OrderItemCreate(BaseModel):
    menu_item_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1)
    notes: Optional[str] = None

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v



class OrderCreate(BaseModel):
    outlet_id: int = Field(..., gt=0, description="ID of the restaurant outlet")
    order_type: OrderType = Field(..., description="Type of order: dine_in, takeaway, or delivery")
    table_id: Optional[int] = Field(None, gt=0, description="Table ID for dine-in orders only")
    items: List[OrderItemCreate] = Field(..., min_items=1, description="List of order items")

    @model_validator(mode='before')
    def validate_order_type_and_table_id(cls, data):
        logger.debug(f"Validating OrderCreate: raw data={data}")
        
        # Ensure order_type is valid
        order_type = data.get('order_type')
        if order_type is None:
            logger.error("Order type is missing or null")
            raise ValueError("Order type is required")
        if not isinstance(order_type, str):
            logger.error(f"Invalid order type: expected string, got {type(order_type)}")
            raise ValueError(f"Order type must be a string, got {type(order_type)}")
        try:
            order_type = OrderType(order_type)
            logger.debug(f"Order type validated: {order_type}")
        except ValueError:
            logger.error(f"Invalid order type: {order_type}. Valid values are: {[e.value for e in OrderType]}")
            raise ValueError(f"Invalid order type: {order_type}. Valid values are: {[e.value for e in OrderType]}")

        # Validate table_id based on order_type
        table_id = data.get('table_id')
        logger.debug(f"Validating table_id={table_id}, order_type={order_type}")
        if order_type == OrderType.DINE_IN and table_id is None:
            logger.error("Validation failed: Table ID is required for dine-in orders")
            raise ValueError("Table ID is required for dine-in orders")
        if order_type != OrderType.DINE_IN and table_id is not None:
            logger.error(f"Validation failed: Table ID {table_id} provided for non-dine-in order (order_type={order_type})")
            raise ValueError(f"Table ID should not be provided for {order_type} orders")
        
        logger.debug("OrderCreate validation successful")
        return data

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True


class OrderResponse(BaseModel):
    id: int
    token_number: str
    outlet_id: int
    table_id: Optional[int]
    order_type: str
    status: str
    total_amount: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class KOTResponse(BaseModel):
    id: int
    order_item_id: int
    status: str

    class Config:
        from_attributes = True

class KOTStatusUpdate(BaseModel):
    status: KOTStatus