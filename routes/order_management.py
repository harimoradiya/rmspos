from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from routes.websocket import notify_kitchen_new_kot, notify_order_status_update

from database import get_db
from models.menu_management import MenuItem
from models.order_management import Order, OrderItem, KOT, OrderStatus, KOTStatus
from models.user import User
from schemas.order_management import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    OrderItemCreate,
    KOTResponse,
    KOTStatusUpdate
)
from utils.auth import get_current_active_user

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

def generate_token_number(db: Session) -> str:
    # Get the latest order to determine the next token number
    latest_order = db.query(Order).order_by(Order.id.desc()).first()
    if not latest_order:
        return "TKN-001"
    
    # Extract the number from the latest token and increment it
    latest_num = int(latest_order.token_number.split('-')[1])
    next_num = latest_num + 1
    return f"TKN-{next_num:03d}"

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Generate token number
        token_number = generate_token_number(db)
        
        # Calculate total amount and create order
        total_amount = 0.0
        db_order = Order(
            token_number=token_number,
            outlet_id=order.outlet_id,
            table_id=order.table_id,
            order_type=order.order_type.value,
            status=OrderStatus.PENDING.value
        )
        db.add(db_order)
        db.flush()  # Get the order ID without committing
        
        # Create order items and KOTs
        for item in order.items:
            # Get menu item price (assuming menu_item relationship exists)
            menu_item = db.query(MenuItem).filter(MenuItem.id == item.menu_item_id).first()
            if not menu_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Menu item {item.menu_item_id} not found"
                )
            
            item_total = menu_item.price * item.quantity
            total_amount += item_total
            
            # Create order item
            db_item = OrderItem(
                order_id=db_order.id,
                menu_item_id=item.menu_item_id,
                quantity=item.quantity,
                price=menu_item.price,
                notes=item.notes
            )
            db.add(db_item)
            db.flush()
            
            # Create KOT for the item
            db_kot = KOT(
                order_item_id=db_item.id,
                status=KOTStatus.PENDING.value
            )
            db.add(db_kot)
            # Send real-time notification to kitchen
            await notify_kitchen_new_kot({
                "id": db_kot.id,
                "item_name": menu_item.name,
                "quantity": item.quantity,
                "notes": item.notes
            })
        
        # Update order total
        db_order.total_amount = total_amount
        
        db.commit()
        db.refresh(db_order)
        return db_order
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating order: {str(e)}"
        )

@router.get("", response_model=List[OrderResponse])
async def list_orders(
    outlet_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Order)
    
    if outlet_id:
        query = query.filter(Order.outlet_id == outlet_id)
    if status:
        query = query.filter(Order.status == status.value)
    
    return query.all()

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    return order

@router.get("/token/{token_number}", response_model=OrderResponse)
async def get_order_by_token(
    token_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    order = db.query(Order).filter(Order.token_number == token_number).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    return order

@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        order.status = status_update.status.value
        order.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(order)
        
        # Send real-time notification about order status update
        await notify_order_status_update({
            "id": order.id,
            "status": order.status
        })
        return order
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating order status: {str(e)}"
        )

@router.post("/{order_id}/items", response_model=OrderResponse)
async def add_order_items(
    order_id: int,
    items: List[OrderItemCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Add new items
        for item in items:
            menu_item = db.query(MenuItem).filter(MenuItem.id == item.menu_item_id).first()
            if not menu_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Menu item {item.menu_item_id} not found"
                )
            
            # Create order item
            db_item = OrderItem(
                order_id=order.id,
                menu_item_id=item.menu_item_id,
                quantity=item.quantity,
                price=menu_item.price,
                notes=item.notes
            )
            db.add(db_item)
            db.flush()
            
            # Create KOT
            db_kot = KOT(
                order_item_id=db_item.id,
                status=KOTStatus.PENDING.value
            )
            db.add(db_kot)
            
            # Update order total
            order.total_amount += menu_item.price * item.quantity
        
        order.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding items to order: {str(e)}"
        )

# KOT Management
@router.get("/kots", response_model=List[KOTResponse])
async def list_kots(
    outlet_id: Optional[int] = None,
    status: Optional[KOTStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(KOT).join(OrderItem).join(Order)
    
    if outlet_id:
        query = query.filter(Order.outlet_id == outlet_id)
    if status:
        query = query.filter(KOT.status == status.value)
    
    return query.all()

@router.put("/kots/{kot_id}/status", response_model=KOTResponse)
async def update_kot_status(
    kot_id: int,
    status_update: KOTStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        kot = db.query(KOT).filter(KOT.id == kot_id).first()
        if not kot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KOT not found"
            )
        
        kot.status = status_update.status.value
        kot.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(kot)
        return kot
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating KOT status: {str(e)}"
        )