from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models.billing import Invoice
from utils.pdf_generator import generate_invoice_pdf

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    # Get invoice and validate
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    base_url = "http://localhost:8000/api/v1/billing"  # Update with actual base URL
    pdf_buffer = generate_invoice_pdf(invoice, base_url)
    
    # Return PDF as downloadable file
    headers = {
        'Content-Disposition': f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    }
    
    return StreamingResponse(
        pdf_buffer,
        media_type='application/pdf',
        headers=headers
    )