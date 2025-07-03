from fastapi import APIRouter, Depends, HTTPException, status,Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging
from typing import List, Optional
from datetime import datetime
from routes.notifications import notify_kitchen_new_kot, notify_order_status_update,notify_kot_status_update

from utils.database import get_db
from models.menu_management import MenuItem,MenuCategory
from models.order_management import Order, OrderItem, KOT, OrderStatus, KOTStatus
from models.user import User
from models.table_management import Table,TableStatus
from models.restaurant_outlet import RestaurantOutlet
from schemas.order_management import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    OrderItemCreate,
    KOTResponse,
    KOTStatusUpdate,
    OrderType,
    OrderStatus
)
from schemas.user import (
    UserRole
)

from utils.auth import get_current_active_user




import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# Dependency for authorized users (superadmin, owner, manager, waiter)
def get_authorized_user(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.WAITER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user

# Dependency for KOT management (superadmin, owner, manager, kitchen_staff)
def get_kot_authorized_user(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.KITCHEN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for KOT management")
    return current_user

# Helper to get authorized outlet IDs
def get_authorized_outlet_ids(current_user: User, db: Session) -> List[int]:
    if current_user.role == UserRole.SUPERADMIN:
        return [outlet.id for outlet in db.query(RestaurantOutlet).all()]
    elif current_user.role == UserRole.OWNER:
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        return [outlet.id for outlet in db.query(RestaurantOutlet).filter(RestaurantOutlet.chain_id.in_(chain_ids)).all()]
    elif current_user.role in [UserRole.MANAGER, UserRole.WAITER, UserRole.KITCHEN]:
        if not current_user.outlet:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not assigned to any outlet")
        return [current_user.outlet.id]
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user role")


def generate_token_number(db: Session, outlet_id: int) -> str:
    print("Generating token number for outlet ID:", outlet_id)
    outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == outlet_id).first()
    if not outlet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    
    latest_order = db.query(Order).filter(Order.outlet_id == outlet_id).order_by(Order.id.desc()).first()
    
    if latest_order is None or latest_order.token_number is None:
        return f"O{outlet_id}-TKN-001"
    
    try:
        latest_num = int(latest_order.token_number.split('-')[-1])
        return f"O{outlet_id}-TKN-{latest_num + 1:03d}"
    except (IndexError, ValueError):
        logger.error(f"Invalid token number format: {latest_order.token_number} for outlet {outlet_id}")
        return f"O{outlet_id}-TKN-001"
    


# Validate KOT status transition
def validate_kot_status_transition(current_status: KOTStatus, new_status: KOTStatus):
    valid_transitions = {
        KOTStatus.PENDING.value: [KOTStatus.PREPARING.value, KOTStatus.CANCELLED.value],
        KOTStatus.PREPARING.value: [KOTStatus.READY.value, KOTStatus.CANCELLED.value],
        KOTStatus.READY.value: [KOTStatus.COMPLETED.value, KOTStatus.CANCELLED.value],
        KOTStatus.COMPLETED.value: [],
        KOTStatus.CANCELLED.value: []
    }
    if new_status not in valid_transitions[current_status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid KOT status transition from {current_status} to {new_status}"
        )

# Update order status based on KOT statuses
def update_order_status(db: Session, order: Order):
    kots = db.query(KOT).filter(KOT.order_item_id.in_(
        db.query(OrderItem.id).filter(OrderItem.order_id == order.id)
    )).all()
    
    if not kots:
        return
    
    kot_statuses = [kot.status for kot in kots]
    if all(status == KOTStatus.COMPLETED.value for status in kot_statuses):
        order.status = OrderStatus.COMPLETED.value
    elif all(status == KOTStatus.READY.value for status in kot_statuses):
        order.status = OrderStatus.READY.value
    elif any(status == KOTStatus.PREPARING.value for status in kot_statuses):
        order.status = OrderStatus.PREPARING.value
    elif any(status == KOTStatus.CANCELLED.value for status in kot_statuses):
        if all(status in [KOTStatus.CANCELLED.value, KOTStatus.COMPLETED.value] for status in kot_statuses):
            order.status = OrderStatus.CANCELLED.value
    order.updated_at = datetime.utcnow()
    
    # Update table status for dine-in orders
    if order.order_type == OrderType.DINE_IN.value and order.table:
        if order.status in [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]:
            order.table.status = TableStatus.AVAILABLE.value
        else:
            order.table.status = TableStatus.OCCUPIED.value
        order.table.updated_at = datetime.utcnow()

# Order Endpoints
@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: Request,
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    logger.debug(f"Raw request body: {await request.json()}")
    logger.debug(f"Parsed OrderCreate: {order.dict()}")
    try:
        # Validate outlet permissions
        authorized_outlet_ids = get_authorized_outlet_ids(current_user, db)
        if order.outlet_id not in authorized_outlet_ids:
            logger.warning(f"User {current_user.id} attempted to create order for unauthorized outlet {order.outlet_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permission to create orders for outlet ID {order.outlet_id}"
            )

        # Validate table if provided
        if order.table_id:
            table = db.query(Table).filter(
                and_(
                    Table.id == order.table_id,
                    # Table.outlet_id == order.outlet_id,
                    Table.status == 'available'
                )
            ).first()
            if not table:
                logger.warning(f"Invalid table {order.table_id} for outlet {order.outlet_id} or table unavailable")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Table ID {order.table_id} is invalid, not associated with outlet ID {order.outlet_id}, or unavailable"
                )

        # Generate token number
        token_number = generate_token_number(db, order.outlet_id)

        # Create order
        total_amount = 0.0
        logger.debug(f"Creating order with order_type={order.order_type}, type={type(order.order_type)}")
        db_order = Order(
            token_number=token_number,
            outlet_id=order.outlet_id,
            table_id=order.table_id,
            order_type=order.order_type,  # Use string directly, not .value
            status=OrderStatus.PENDING.value,
            # created_by_id=current_user.id
        )
        db.add(db_order)
        db.flush()

        # Process order items
        for item in order.items:
            menu_item = db.query(MenuItem).filter(
                and_(
                    MenuItem.id == item.menu_item_id,
                    # MenuItem.outlet_id == order.outlet_id,
                    MenuItem.is_available == True
                )
            ).first()
            if not menu_item:
                logger.warning(f"Menu item {item.menu_item_id} not found or unavailable for outlet {order.outlet_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Menu item ID {item.menu_item_id} not found, inactive, or not associated with outlet ID {order.outlet_id}"
                )

            item_total = menu_item.price * item.quantity
            total_amount += item_total

            db_item = OrderItem(
                order_id=db_order.id,
                menu_item_id=item.menu_item_id,
                quantity=item.quantity,
                price=menu_item.price,
                notes=item.notes
            )
            db.add(db_item)
            db.flush()

            db_kot = KOT(
                order_item_id=db_item.id,
                status=KOTStatus.PENDING.value
            )
            
            db.add(db_kot)
            db.flush()
            try:
                await notify_kitchen_new_kot({
                    "outlet_id": db_order.outlet_id,  
                    "id": db_kot.id,
                    "order_id": db_order.id,
                    "item_name": menu_item.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.debug(f"Sent KOT notification for KOT {db_kot.id} for order {db_order.id}")
            except Exception as e:
                logger.warning(f"Failed to send KOT notification for KOT {db_kot.id}: {str(e)}")

        # Update order total and table status
        db_order.total_amount = total_amount
        if order.table_id:
            table.status = 'occupied'
        db.commit()
        db.refresh(db_order)
        logger.info(f"Order {db_order.id} created by user {current_user.id} for outlet {order.outlet_id}")
        return db_order

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error for order creation by user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order by user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )

 
    
@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    order = db.query(Order).filter(
        and_(
            Order.id == order_id,
            Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
        )
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or unauthorized")
    return order

@router.get("/token/{token_number}", response_model=OrderResponse)
async def get_order_by_token(
    token_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    order = db.query(Order).filter(
        and_(
            Order.token_number == token_number,
            Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
        )
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or unauthorized")
    return order

@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    try:
        order = db.query(Order).filter(
            and_(
                Order.id == order_id,
                Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
            )
        ).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or unauthorized")

        # Validate status transition
        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
            OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.COMPLETED],
            OrderStatus.COMPLETED: [],
            OrderStatus.CANCELLED: []
        }
        if status_update.status not in valid_transitions[OrderStatus(order.status)]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {order.status} to {status_update.status}"
            )

        order.status = status_update.status.value
        order.updated_at = datetime.utcnow()

        # Update table status if applicable
        if order.table_id:
            table = db.query(Table).filter(Table.id == order.table_id).first()
            if status_update.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
                table.status = 'available'
            elif status_update.status == OrderStatus.PREPARING:
                table.status = 'occupied'

        db.commit()
        db.refresh(order)
        await notify_order_status_update({
            "id": order.id,
            "status": order.status,
            "outlet_id": order.outlet_id
        })
        logger.info(f"Order {order_id} status updated to {status_update.status} by user {current_user.id}")
        return order

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating order {order_id} status: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update order status")

@router.post("/{order_id}/items", response_model=OrderResponse)
async def add_order_items(
    order_id: int,
    items: List[OrderItemCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    try:
        order = db.query(Order).filter(
            and_(
                Order.id == order_id,
                Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
            )
        ).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or unauthorized")

        if order.status not in [OrderStatus.PENDING.value, OrderStatus.PREPARING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add items to order in current status"
            )
        

        # Validate outlet
        outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == order.outlet_id).first()
        if not outlet:
            logger.warning(f"Outlet {order.outlet_id} not found for order {order_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Outlet ID {order.outlet_id} not found")

        # Process order items and KOTs
        new_kots = []
        for item in items:
            # Validate menu item
            menu_item = db.query(MenuItem).join(MenuCategory).filter(
                and_(
                    MenuItem.id == item.menu_item_id,
                    MenuItem.is_available == True,
                    or_(
                        MenuCategory.outlet_id == order.outlet_id,
                        MenuCategory.chain_id == outlet.chain_id
                    )
                )
            ).first()
            if not menu_item:
                logger.warning(f"Menu item {item.menu_item_id} not found or unavailable for outlet {order.outlet_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Menu item ID {item.menu_item_id} not found, inactive, or not associated with outlet ID {order.outlet_id}"
                )

            # Create OrderItem
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
                status=KOTStatus.PENDING
            )
            db.add(db_kot)
            db.flush()
            new_kots.append(db_kot)

            # Update order total
            order.total_amount += menu_item.price * item.quantity

            # Send KOT notification
            try:
                await notify_kitchen_new_kot({
                    "outlet_id": order.outlet_id,  # Include outlet_id
                    "id": db_kot.id,
                    "order_id": order.id,
                    "item_name": menu_item.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.debug(f"Sent KOT notification for KOT {db_kot.id} for order {order.id}")
            except Exception as e:
                logger.warning(f"Failed to send KOT notification for KOT {db_kot.id}: {str(e)}")

        # Update order and table status
        order.updated_at = datetime.utcnow()
        order.update_table_status(db)  # Update table status
        db.commit()
        db.refresh(order)

        logger.info(f"Added {len(items)} items to order {order_id} by user {current_user.id} with {len(new_kots)} KOTs")
        return order

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error adding items to order {order_id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding items to order {order_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add items: {str(e)}")

@router.post("/{order_id}/kots/{kot_id}/status", response_model=KOTResponse)
async def update_kot_status(
    order_id: int,
    kot_id: int,
    status_update: KOTStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kot_authorized_user)
):
    try:
        # Validate KOT and order
        kot = db.query(KOT).join(OrderItem).join(Order).filter(
            and_(
                KOT.id == kot_id,
                OrderItem.order_id == order_id,
                Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
            )
        ).first()
        if not kot:
            logger.warning(f"KOT {kot_id} not found or unauthorized for order {order_id} by user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KOT not found or unauthorized"
            )

        # Restrict cancellation to managers or above
        if status_update.status == KOTStatus.CANCELLED.value and current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER]:
            logger.warning(f"User {current_user.id} attempted to cancel KOT {kot_id} without permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only managers or above can cancel KOTs"
            )

        # Validate status transition
        validate_kot_status_transition(kot.status, status_update.status)

        # Update KOT status
        kot.status = status_update.status
        kot.updated_at = datetime.utcnow()
        db.flush()

        # Update order status based on KOTs
        order = kot.order_item.order
        update_order_status(db, order)

        # Notify kitchen of KOT status update
        try:
            await notify_kot_status_update({
                "id": kot.id,
                "status": kot.status,
                "order_id": order.id,
                "outlet_id": order.outlet_id,
                "item_name": kot.order_item.menu_item.name,
                "quantity": kot.order_item.quantity,
                "notes": kot.order_item.notes
            })
        except Exception as e:
            logger.warning(f"Failed to send KOT status notification for KOT {kot.id}: {str(e)}")

        db.commit()
        db.refresh(kot)
        logger.info(f"KOT {kot.id} status updated to {status_update.status} by user {current_user.id}")
        return kot

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error for KOT {kot_id} status update by user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating KOT {kot_id} status by user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KOT status: {str(e)}"
        )

@router.get("/{order_id}/kots", response_model=List[KOTResponse])
async def list_kots_by_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kot_authorized_user)
):
    order = db.query(Order).filter(
        and_(
            Order.id == order_id,
            Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
        )
    ).first()
    if not order:
        logger.warning(f"Order {order_id} not found or unauthorized for user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or unauthorized")

    kots = db.query(KOT).join(OrderItem).filter(OrderItem.order_id == order_id).all()
    logger.info(f"Retrieved {len(kots)} KOTs for order {order_id} by user {current_user.id}")
    return kots

@router.get("/outlet/{outlet_id}/kots", response_model=List[KOTResponse])
async def list_kots_by_outlet(
    outlet_id: int,
    kotstatus: Optional[KOTStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kot_authorized_user)
):
    if outlet_id not in get_authorized_outlet_ids(current_user, db):
        logger.warning(f"User {current_user.id} attempted to list KOTs for unauthorized outlet {outlet_id}")
        raise HTTPException(status_code= status.HTTP_403_FORBIDDEN, detail="No permission for this outlet")

    query = db.query(KOT).join(OrderItem).join(Order).filter(Order.outlet_id == outlet_id)
    if kotstatus:
        query = query.filter(KOT.status == kotstatus.value)
    kots = query.all()
    
    logger.info(f"Retrieved {len(kots)} KOTs for outlet {outlet_id} by user {current_user.id}")
    return kots