from fastapi import APIRouter, Depends, HTTPException,WebSocket, WebSocketDisconnect, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List,Dict,Optional
from database import get_db

from schemas.billing import InvoiceCreate, InvoiceResponse, SplitBillRequest
from models.user import User, UserRole
from models.billing import Invoice, Payment, SplitBill, PaymentStatus,InvoiceStatus
from models.order_management import Order, OrderStatus
from models.table_management import TableStatus
from utils.auth import get_current_active_user
from models.restaurant_outlet import RestaurantOutlet
import json
from datetime import datetime
from utils.pdf_generator import generate_receipt_pdf
import logging




logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}  # outlet_id -> List[WebSocket]

    async def connect(self, websocket: WebSocket, outlet_id: int):
        await websocket.accept()
        if outlet_id not in self.active_connections:
            self.active_connections[outlet_id] = []
        self.active_connections[outlet_id].append(websocket)
        logger.debug(f"WebSocket connected for outlet {outlet_id}. Total connections: {len(self.active_connections[outlet_id])}")

    def disconnect(self, websocket: WebSocket, outlet_id: int):
        if outlet_id in self.active_connections:
            self.active_connections[outlet_id].remove(websocket)
            if not self.active_connections[outlet_id]:
                del self.active_connections[outlet_id]
            logger.debug(f"WebSocket disconnected for outlet {outlet_id}. Total connections: {len(self.active_connections.get(outlet_id, []))}")

    async def broadcast(self, message: dict, outlet_id: int):
        if outlet_id in self.active_connections:
            for connection in self.active_connections[outlet_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send WebSocket message to outlet {outlet_id}: {str(e)}")

connection_manager = ConnectionManager()

# Notify order status update
async def notify_order_status_update(data: dict):
    outlet_id = data.get("outlet_id")
    if not outlet_id:
        logger.warning("No outlet_id provided in notify_order_status_update")
        return

    logger.debug(f"Sending order status update for outlet {outlet_id}: {data}")
    try:
        await connection_manager.broadcast(data, outlet_id)
    except Exception as e:
        logger.warning(f"Failed to broadcast order status update for outlet {outlet_id}: {str(e)}")

# WebSocket endpoint for order status updates
@router.websocket("/ws/order-status/{outlet_id}")
async def websocket_order_status(websocket: WebSocket, outlet_id: int, db: Session = Depends(get_db)):
    # Validate outlet
    outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == outlet_id).first()
    if not outlet:
        await websocket.close(code=4000, reason="Invalid outlet ID")
        return

    try:
        await connection_manager.connect(websocket, outlet_id)
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, outlet_id)
    except Exception as e:
        logger.error(f"WebSocket error for outlet {outlet_id}: {str(e)}")
        connection_manager.disconnect(websocket, outlet_id)
        await websocket.close(code=4000, reason=str(e))


# Dependency for authorized users (superadmin, owner, manager)
def get_authorized_user(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user

# Helper to get authorized outlet IDs
def get_authorized_outlet_ids(current_user: User, db: Session) -> List[int]:
    if current_user.role == UserRole.SUPERADMIN:
        return [outlet.id for outlet in db.query(RestaurantOutlet).all()]
    elif current_user.role == UserRole.OWNER:
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        return [outlet.id for outlet in db.query(RestaurantOutlet).filter(RestaurantOutlet.chain_id.in_(chain_ids)).all()]
    elif current_user.role == UserRole.MANAGER:
        if not current_user.outlet:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not assigned to any outlet")
        return [current_user.outlet.id]
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user role")

# Generate outlet-specific invoice number
def generate_invoice_number(db: Session, outlet_id: int) -> str:
    outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == outlet_id).first()
    if not outlet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    
    latest_invoice = db.query(Invoice).filter(Invoice.order_id.in_(
        db.query(Order.id).filter(Order.outlet_id == outlet_id)
    )).order_by(Invoice.id.desc()).first()
    
    if not latest_invoice or not latest_invoice.invoice_number:
        return f"O{outlet_id}-INV-001"
    
    
    try:
        latest_num = int(latest_invoice.invoice_number.split('-')[-1])
        return f"{outlet.name[:3].upper()}-INV-{latest_num + 1:03d}"
    except (IndexError, ValueError):
        logger.error(f"Invalid invoice number format: {latest_invoice.invoice_number}")
        return f"{outlet.name[:3].upper()}-INV-001"

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    request: Request,
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    logger.debug(f"Raw request body: {await request.json()}")
    logger.debug(f"Parsed InvoiceCreate: {invoice_data.dict()}")
    try:
        # Validate order
        order = db.query(Order).filter(Order.id == invoice_data.order_id).first()
        if not order:
            logger.warning(f"Order {invoice_data.order_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
        # Check user permissions
        authorized_outlet_ids = get_authorized_outlet_ids(current_user, db)
        if order.outlet_id not in authorized_outlet_ids:
            logger.warning(f"User {current_user.id} attempted to invoice order {order.id} for unauthorized outlet {order.outlet_id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission for this outlet")

        # Validate order status
        if order.status not in [OrderStatus.READY.value, OrderStatus.COMPLETED.value]:
            logger.warning(f"Order {order.id} has invalid status {order.status} for invoicing")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order must be in READY or COMPLETED status")

        # Check for existing invoice
        existing_invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
        if existing_invoice:
            logger.warning(f"Invoice already exists for order {order.id}: invoice {existing_invoice.id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already exists for this order")

        # Validate payment amounts
        # total_payments = sum(payment.amount for payment in invoice_data.payments)
        calculated_total = order.total_amount
        # if total_payments < calculated_total:
        #     logger.warning(f"Payment total {total_payments} is less than invoice total {calculated_total} for order {order.id}")
        #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amounts must cover the invoice total")

        # Generate invoice number
        invoice_number = generate_invoice_number(db, order.outlet_id)

        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            order_id=order.id,
            subtotal=order.total_amount,
            discount=invoice_data.discount,
            tax=invoice_data.tax,
            total_amount=calculated_total,
            status=InvoiceStatus.PENDING.value,
            created_by_id=current_user.id
        )
        db.add(invoice)
        db.flush()

        # Create payments
        for payment_data in invoice_data.payments:
            payment = Payment(
                invoice_id=invoice.id,
                amount= order.total_amount,
                method=payment_data.method,
                status=PaymentStatus.PENDING.value
            )
            db.add(payment)

        db.commit()
        db.refresh(invoice)
        logger.info(f"Invoice {invoice.id} created by user {current_user.id} for order {order.id}")
        return invoice

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error for invoice creation by user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating invoice by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create invoice: {str(e)}")


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db),   current_user: User = Depends(get_authorized_user)):
    
    # Get invoice and validate
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    base_url = "http://localhost:8000/api/v1/billing"  # Update with actual base URL
    pdf_buffer = generate_receipt_pdf(invoice, base_url)
    
    # Return PDF as downloadable file
    headers = {
        'Content-Disposition': f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    }
    
    return StreamingResponse(
        pdf_buffer,
        media_type='application/pdf',
        headers=headers
    )

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    invoice = db.query(Invoice).join(Order).filter(
        and_(
            Invoice.id == invoice_id,
            Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
        )
    ).first()
    if not invoice:
        logger.warning(f"Invoice {invoice_id} not found or unauthorized for user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found or unauthorized")
    return invoice

@router.get("/invoices/order/{order_id}", response_model=List[InvoiceResponse])
async def list_invoices_by_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.warning(f"Order {order_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    if order.outlet_id not in get_authorized_outlet_ids(current_user, db):
        logger.warning(f"User {current_user.id} attempted to list invoices for unauthorized order {order_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission for this order")

    invoices = db.query(Invoice).filter(Invoice.order_id == order_id).all()
    logger.info(f"Retrieved {len(invoices)} invoices for order {order_id} by user {current_user.id}")
    return invoices

@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
async def complete_payment(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    try:
        invoice = db.query(Invoice).join(Order).filter(
            and_(
                Invoice.id == invoice_id,
                Order.outlet_id.in_(get_authorized_outlet_ids(current_user, db))
            )
        ).first()
        if not invoice:
            logger.warning(f"Invoice {invoice_id} not found or unauthorized for user {current_user.id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found or unauthorized")

        if invoice.status == InvoiceStatus.COMPLETED.value:
            logger.warning(f"Invoice {invoice_id} is already completed")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is already paid")

        # Update payment status
        for payment in invoice.payments:
            if payment.status != PaymentStatus.COMPLETED.value:
                payment.status = PaymentStatus.COMPLETED.value
                payment.updated_at = datetime.utcnow()

        # Update invoice status
        invoice.status = InvoiceStatus.COMPLETED.value
        invoice.updated_at = datetime.utcnow()

        # Update order status
        order = invoice.order
        if order.status != OrderStatus.COMPLETED.value:
            order.status = OrderStatus.COMPLETED.value
            order.updated_at = datetime.utcnow()

            # Update table status if dine-in order
            if order.order_type == "dine_in" and order.table:
                order.table.status = TableStatus.AVAILABLE.value
                order.table.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(invoice)
        logger.info(f"Payment completed for invoice {invoice.id} by user {current_user.id}")

        # Notify order status update
        try:
            await notify_order_status_update({
                "id": order.id,
                "status": order.status,
                "outlet_id": order.outlet_id
            })
        except Exception as e:
            logger.warning(f"Failed to send order status notification for order {order.id}: {str(e)}")

        return invoice

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error for payment completion by user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error completing payment for invoice {invoice_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to complete payment: {str(e)}")

@router.post("/split-bill", response_model=List[InvoiceResponse], status_code=status.HTTP_201_CREATED)
async def split_bill(
    request: Request,
    split_data: SplitBillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    logger.debug(f"Raw request body: {await request.json()}")
    logger.debug(f"Parsed SplitBillRequest: {split_data.dict()}")
    try:
        # Validate order
        order = db.query(Order).filter(Order.id == split_data.order_id).first()
        if not order:
            logger.warning(f"Order {split_data.order_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # Check user permissions
        if order.outlet_id not in get_authorized_outlet_ids(current_user, db):
            logger.warning(f"User {current_user.id} attempted to split bill for unauthorized order {order.id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission for this order")

        # Validate order status
        if order.status not in [OrderStatus.READY.value, OrderStatus.COMPLETED.value]:
            logger.warning(f"Order {order.id} has invalid status {order.status} for split billing")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order must be in READY or COMPLETED status")

        # Check for existing invoice
        existing_invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
        if existing_invoice:
            logger.warning(f"Invoice already exists for order {order.id}: invoice {existing_invoice.id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already exists for this order")

        # Validate split type
        if split_data.split_by not in ["items", "amount"]:
            logger.warning(f"Invalid split type {split_data.split_by} for order {order.id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Split type must be 'items' or 'amount'")

        invoices = []
        if split_data.split_by == "items":
            # Validate item IDs
            order_item_ids = {item.id for item in order.items}
            split_item_ids = set()
            for split in split_data.splits:
                invalid_ids = set(split.item_ids) - order_item_ids
                if invalid_ids:
                    logger.warning(f"Invalid item IDs {invalid_ids} in split for order {order.id}")
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid item IDs: {invalid_ids}")
                split_item_ids.update(split.item_ids)
            
            # Ensure all items are included
            missing_ids = order_item_ids - split_item_ids
            if missing_ids:
                logger.warning(f"Missing item IDs {missing_ids} in split for order {order.id}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"All order items must be included in splits. Missing IDs: {missing_ids}")

            # Calculate proportional tax and discount
            total_subtotal = order.total_amount
            total_discount = split_data.discount or 0.0
            total_tax = split_data.tax or 0.0

            for split in split_data.splits:
                # Calculate subtotal for split
                subtotal = sum(item.price * item.quantity for item in order.items if item.id in split.item_ids)
                if subtotal == 0:
                    logger.warning(f"Empty split (subtotal=0) for order {order.id}")
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Split cannot have zero subtotal")

                # Proportional discount and tax
                proportion = subtotal / total_subtotal if total_subtotal > 0 else 0
                split_discount = total_discount * proportion
                split_tax = total_tax * proportion
                total_amount = subtotal - split_discount + split_tax

                # Create invoice
                invoice = Invoice(
                    invoice_number=generate_invoice_number(db, order.outlet_id),
                    order_id=order.id,
                    subtotal=subtotal,
                    discount=split_discount,
                    tax=split_tax,
                    total_amount=total_amount,
                    status=InvoiceStatus.PENDING.value,
                    created_by_id=current_user.id
                )
                db.add(invoice)
                db.flush()

                # Create split bill record
                split_bill = SplitBill(
                    invoice_id=invoice.id,
                    split_type=split_data.split_by,
                    split_data=json.dumps({"item_ids": split.item_ids})
                )
                db.add(split_bill)
                invoices.append(invoice)

        elif split_data.split_by == "amount":
            # Validate split amounts
            total_split_amount = sum(split.amount for split in split_data.splits)
            expected_total = order.total_amount - (split_data.discount or 0.0) + (split_data.tax or 0.0)
            if total_split_amount != expected_total:
                logger.warning(f"Split amounts {total_split_amount} do not match expected total {expected_total} for order {order.id}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Split amounts must equal the order total minus discount plus tax")

            for split in split_data.splits:
                if split.amount <= 0:
                    logger.warning(f"Invalid split amount {split.amount} for order {order.id}")
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Split amount must be positive")

                # Create invoice
                invoice = Invoice(
                    invoice_number=generate_invoice_number(db, order.outlet_id),
                    order_id=order.id,
                    subtotal=split.amount,
                    discount=0.0,  # Discount applied at order level
                    tax=0.0,      # Tax applied at order level
                    total_amount=split.amount,
                    status=InvoiceStatus.PENDING.value,
                    created_by_id=current_user.id
                )
                db.add(invoice)
                db.flush()

                # Create split bill record
                split_bill = SplitBill(
                    invoice_id=invoice.id,
                    split_type=split_data.split_by,
                    split_data=json.dumps({"amount": split.amount})
                )
                db.add(split_bill)
                invoices.append(invoice)

        db.commit()
        for invoice in invoices:
            db.refresh(invoice)
        logger.info(f"Created {len(invoices)} split invoices for order {order.id} by user {current_user.id}")
        return invoices

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Validation error for split bill creation by user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating split bill for order {split_data.order_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create split bill: {str(e)}")