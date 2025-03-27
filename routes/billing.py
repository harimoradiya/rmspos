from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.billing import Invoice, Payment, SplitBill, PaymentStatus
from models.order_management import Order, OrderStatus
from models.table_management import TableStatus
from schemas.billing import InvoiceCreate, InvoiceResponse, SplitBillRequest, SplitBillResponse
import json
from datetime import datetime

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

def generate_invoice_number():
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"INV-{timestamp}"

@router.post("/invoices", response_model=InvoiceResponse)
def create_invoice(invoice_data: InvoiceCreate, db: Session = Depends(get_db)):
    # Get order and validate
    order = db.query(Order).filter(Order.id == invoice_data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Create invoice
    invoice = Invoice(
        invoice_number=generate_invoice_number(),
        order_id=order.id,
        subtotal=order.total_amount,
        discount=invoice_data.discount,
        tax=invoice_data.tax,
        total_amount=order.total_amount - invoice_data.discount + invoice_data.tax
    )
    db.add(invoice)
    
    # Create payments
    for payment_data in invoice_data.payments:
        payment = Payment(
            invoice_id=invoice.id,
            amount=payment_data.amount,
            method=payment_data.method
        )
        db.add(payment)
    
    db.commit()
    db.refresh(invoice)
    return invoice

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.get("/invoices/order/{order_id}", response_model=List[InvoiceResponse])
def list_invoices_by_order(order_id: int, db: Session = Depends(get_db)):
    invoices = db.query(Invoice).filter(Invoice.order_id == order_id).all()
    return invoices

@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
def complete_payment(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Update payment status
    for payment in invoice.payments:
        payment.status = PaymentStatus.COMPLETED
    
    # Update order status
    order = invoice.order
    order.status = OrderStatus.COMPLETED
    
    # Update table status if dine-in order
    if order.order_type == "dine_in" and order.table:
        order.table.status = TableStatus.AVAILABLE
    
    db.commit()
    db.refresh(invoice)
    return invoice

@router.post("/split-bill", response_model=List[InvoiceResponse])
def split_bill(split_data: SplitBillRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == split_data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    invoices = []
    for split in split_data.splits:
        # Calculate subtotal for split
        subtotal = sum(item.price * item.quantity 
                      for item in order.items 
                      if item.id in split.item_ids)
        
        # Create invoice for split
        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            order_id=order.id,
            subtotal=subtotal,
            total_amount=subtotal
        )
        db.add(invoice)
        
        # Create split bill record
        split_bill = SplitBill(
            invoice_id=invoice.id,
            split_type=split_data.split_by,
            split_data=json.dumps({"item_ids": split.item_ids})
        )
        db.add(split_bill)
        invoices.append(invoice)
    
    db.commit()
    for invoice in invoices:
        db.refresh(invoice)
    
    return invoices