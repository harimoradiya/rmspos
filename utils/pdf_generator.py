from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
from datetime import datetime
import qrcode
import io

def generate_invoice_pdf(invoice, base_url):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, "INVOICE")
    
    # Invoice details
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Invoice Number: {invoice.invoice_number}")
    c.drawString(50, height - 100, f"Date: {invoice.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    # Order details
    c.drawString(50, height - 130, f"Order Token: {invoice.order.token_number}")
    if invoice.order.table_id:
        c.drawString(50, height - 150, f"Table: {invoice.order.table_id}")
    c.drawString(50, height - 170, f"Order Type: {invoice.order.order_type}")

    # Items table header
    y = height - 220
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Item")
    c.drawString(250, y, "Qty")
    c.drawString(350, y, "Price")
    c.drawString(450, y, "Subtotal")
    c.line(50, y - 5, 550, y - 5)
    
    # Items
    y -= 30
    c.setFont("Helvetica", 12)
    for item in invoice.order.items:
        c.drawString(50, y, item.menu_item.name)
        c.drawString(250, y, str(item.quantity))
        c.drawString(350, y, f"${item.price:.2f}")
        c.drawString(450, y, f"${item.price * item.quantity:.2f}")
        y -= 20

    # Totals
    y -= 30
    c.line(50, y + 5, 550, y + 5)
    c.drawString(350, y, "Subtotal:")
    c.drawString(450, y, f"${invoice.subtotal:.2f}")
    y -= 20
    c.drawString(350, y, "Discount:")
    c.drawString(450, y, f"${invoice.discount:.2f}")
    y -= 20
    c.drawString(350, y, "Tax:")
    c.drawString(450, y, f"${invoice.tax:.2f}")
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Total:")
    c.drawString(450, y, f"${invoice.total_amount:.2f}")

    # Payment details
    y -= 50
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Payment Details")
    y -= 20
    c.setFont("Helvetica", 12)
    for payment in invoice.payments:
        c.drawString(50, y, f"Method: {payment.method}")
        c.drawString(250, y, f"Amount: ${payment.amount:.2f}")
        c.drawString(450, y, f"Status: {payment.status}")
        y -= 20

    # QR Code
    qr_code = QrCodeWidget(f"{base_url}/invoices/{invoice.id}")
    qr_bounds = qr_code.getBounds()
    qr_width = 100
    qr_height = 100
    qr_x = (width - qr_width) / 2
    qr_y = 50
    
    d = Drawing(qr_width, qr_height, transform=[qr_width/qr_bounds[2], 0, 0, qr_height/qr_bounds[3], 0, 0])
    d.add(qr_code)
    renderPDF.draw(d, c, qr_x, qr_y)
    
    c.setFont("Helvetica", 10)
    c.drawString((width - 200) / 2, 30, "Scan to view invoice online")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer