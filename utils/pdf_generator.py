from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from models.billing import Invoice
from fastapi import HTTPException
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_receipt_pdf(invoice: Invoice, base_url: str) -> BytesIO:
    """
    Generate a well-structured receipt-style invoice (4" wide)
    Optimized for thermal printers with all relevant information
    """
    buffer = BytesIO()
    receipt_width = 4 * inch
    receipt_height = 8 * inch
    c = canvas.Canvas(buffer, pagesize=(receipt_width, receipt_height))
    
    try:
        margin = 0.2 * inch
        y_pos = receipt_height - margin
        
        # Business Header
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(receipt_width / 2, y_pos, "Your Restaurant")
        y_pos -= 0.2 * inch
        c.setFont("Helvetica", 8)
        c.drawCentredString(receipt_width / 2, y_pos, "123 Main St, City, ST 12345")
        y_pos -= 0.15 * inch
        c.drawCentredString(receipt_width / 2, y_pos, "Contact: (555) 123-4567")
        y_pos -= 0.15 * inch
        c.drawCentredString(receipt_width / 2, y_pos, "GST No: 24ABTPA0683M1ZE")
        y_pos -= 0.25 * inch

        # Invoice Details
        c.setFont("Helvetica-Bold", 9)
        current_time = datetime.now().strftime('%I:%M %p IST')
        current_date = datetime.now().strftime('%d-%m-%Y')
        c.drawString(margin, y_pos, f"Bill No: {invoice.invoice_number}")
        c.drawRightString(receipt_width - margin, y_pos, f"Date: {current_date}")
        y_pos -= 0.15 * inch
        c.drawString(margin, y_pos, f"Time: {current_time}")
        y_pos -= 0.2 * inch

        # Item Header
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, y_pos, "DESCRIPTION")
        c.drawCentredString(receipt_width / 2, y_pos, "QTY")
        c.drawRightString(receipt_width - margin, y_pos, "AMOUNT")
        y_pos -= 0.15 * inch
        c.line(margin, y_pos, receipt_width - margin, y_pos)
        y_pos -= 0.15 * inch

        # Items List
        c.setFont("Helvetica", 8)
        total_amount = 0.0
        if invoice.order and invoice.order.items:
            for item in invoice.order.items:
                item_name = item.menu_item.name if item.menu_item else "Unknown Item"
                if len(item_name) > 25:
                    item_name = item_name[:22] + "..."
                qty = item.quantity or 0
                price = item.price or 0
                amount = qty * price
                total_amount += amount
                c.drawString(margin + 0.1 * inch, y_pos, item_name)
                c.drawCentredString(receipt_width / 2, y_pos, str(qty))
                c.drawRightString(receipt_width - margin - 0.1 * inch, y_pos, f"₹{amount:.2f}")
                y_pos -= 0.2 * inch

        # Totals and Taxes
        c.line(margin, y_pos, receipt_width - margin, y_pos)
        y_pos -= 0.15 * inch
        c.setFont("Helvetica", 8)
        c.drawString(margin, y_pos, "Subtotal:")
        c.drawRightString(receipt_width - margin, y_pos, f"₹{total_amount:.2f}")
        y_pos -= 0.15 * inch
        if invoice.tax:
            tax_amount = total_amount * (invoice.tax / 100)
            c.drawString(margin, y_pos, f"Tax ({invoice.tax:.1f}%):")
            c.drawRightString(receipt_width - margin, y_pos, f"₹{tax_amount:.2f}")
            y_pos -= 0.15 * inch
            total_amount += tax_amount
        if invoice.discount and invoice.discount > 0:
            c.drawString(margin, y_pos, f"Discount:")
            c.drawRightString(receipt_width - margin, y_pos, f"-₹{invoice.discount:.2f}")
            y_pos -= 0.15 * inch
            total_amount -= invoice.discount
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y_pos, "NET TOTAL:")
        c.drawRightString(receipt_width - margin, y_pos, f"₹{total_amount:.2f}")
        y_pos -= 0.25 * inch

        # Payment Info
        if invoice.payments:
            c.setFont("Helvetica", 8)
            for payment in invoice.payments:
                amount_str = f"₹{payment.amount:.2f}" if payment.amount is not None else "₹0.00"
                status_value = payment.status
                status_text = status_value.value if hasattr(status_value, 'value') else \
                             status_value.name if hasattr(status_value, 'name') else \
                             str(status_value) if status_value else 'N/A'
                method_value = payment.method
                method_text = method_value.value if hasattr(method_value, 'value') else \
                             method_value.name if hasattr(method_value, 'name') else \
                             str(method_value) if method_value else 'N/A'
                payment_line = f"Payment Method: {method_text}  Amount: {amount_str}  Status: {status_text}"
                c.drawString(margin, y_pos, payment_line)
                y_pos -= 0.15 * inch

        # Footer
        c.line(margin, y_pos, receipt_width - margin, y_pos)
        y_pos -= 0.15 * inch
        c.setFont("Helvetica", 8)
        c.drawCentredString(receipt_width / 2, y_pos, "Thank you for your visit!")
        y_pos -= 0.15 * inch
        c.drawCentredString(receipt_width / 2, y_pos, "Visit us at: yourrestaurant.com")
        y_pos -= 0.15 * inch
        c.drawCentredString(receipt_width / 2, y_pos, "Powered by RMS POS Pro")

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    except Exception as e:
        logger.error(f"Error generating receipt PDF for invoice {invoice.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate receipt PDF: {str(e)}")