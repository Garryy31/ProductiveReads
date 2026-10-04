from io import BytesIO
from xml.sax.saxutils import escape
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def invoice_data(order, items):
    line_items = []
    subtotal = 0
    charged_total = 0
    for item in items:
        item_subtotal = item["price"] * item["quantity"]
        item_original = item["original_price"] * item["quantity"]
        line_items.append({"title": item["title"], "author": item["author"], "quantity": item["quantity"], "price": item["price"], "amount": item_subtotal})
        subtotal += item_original
        charged_total += item_subtotal
    discount = max(0, subtotal - charged_total)
    tax = 0
    grand_total = order["total_amount"] + tax
    return {"invoice_number": f"PR-{order['id']:06d}", "invoice_date": datetime.now().strftime("%d %b %Y, %I:%M %p"), "items": line_items, "subtotal": subtotal, "discount": discount, "tax": tax, "grand_total": grand_total}


def build_invoice(order, items):
    data = invoice_data(order, items)
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor("#14213d"), spaceAfter=4)
    subtitle = ParagraphStyle("InvoiceSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#667085"))
    body = ParagraphStyle("InvoiceBody", parent=styles["Normal"], fontSize=9, leading=12)
    story = [Paragraph("PRODUCTIVEREADS", title), Paragraph("Self-Growth & Productivity Book Store", subtitle), Spacer(1, 12)]
    details = [[Paragraph(f"<b>Invoice Number:</b> {data['invoice_number']}", body), Paragraph(f"<b>Invoice Date:</b> {data['invoice_date']}", body)], [Paragraph(f"<b>Order ID:</b> #{order['id']}", body), Paragraph(f"<b>Payment Status:</b> {order['payment_status']}", body)]]
    details_table = Table(details, colWidths=[85 * mm, 85 * mm])
    details_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f4f6")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe3e8")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dfe3e8")), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.extend([details_table, Spacer(1, 18), Paragraph("<b>Customer Information</b>", body), Spacer(1, 5)])
    customer = [[Paragraph(f"Name: {escape(str(order['customer_name']))}", body)], [Paragraph(f"Email: {escape(str(order['email']))}", body)], [Paragraph(f"Phone: {escape(str(order['phone']))}", body)], [Paragraph(f"Address: {escape(str(order['address']))}, {escape(str(order['city']))}, {escape(str(order['state']))} - {escape(str(order['pincode']))}", body)]]
    story.extend([Table(customer, colWidths=[170 * mm], style=TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe3e8")), ("PADDING", (0, 0), (-1, -1), 7)])), Spacer(1, 18)])
    rows = [["Book Name", "Author", "Qty", "Price", "Subtotal"]]
    for item in data["items"]:
        rows.append([item["title"], item["author"], str(item["quantity"]), f"Rs. {item['price']:.2f}", f"Rs. {item['amount']:.2f}"])
    book_table = Table(rows, colWidths=[58 * mm, 43 * mm, 15 * mm, 24 * mm, 30 * mm], repeatRows=1)
    book_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dfe3e8")), ("PADDING", (0, 0), (-1, -1), 7), ("ALIGN", (2, 1), (-1, -1), "RIGHT")]))
    story.extend([book_table, Spacer(1, 15)])
    totals = [["Subtotal", f"Rs. {data['subtotal']:.2f}"], ["Discount", f"- Rs. {data['discount']:.2f}"], ["Tax", f"Rs. {data['tax']:.2f}"], ["Grand Total", f"Rs. {data['grand_total']:.2f}"]]
    totals_table = Table(totals, colWidths=[140 * mm, 30 * mm])
    totals_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dff2e9")), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("PADDING", (0, 0), (-1, -1), 9)]))
    story.extend([totals_table, Spacer(1, 18), Paragraph("<b>Payment Details</b>", body), Spacer(1, 8), Paragraph(f"Payment Method: Razorpay &nbsp;&nbsp; | &nbsp;&nbsp; Payment Status: PAID", body), Paragraph(f"Razorpay Order ID: {escape(str(order['razorpay_order_id']))}", body), Paragraph(f"Razorpay Payment ID: {escape(str(order['razorpay_payment_id']))}", body), Spacer(1, 30), Paragraph("Thank you for choosing ProductiveReads.<br/><b>Read. Grow. Achieve.</b>", subtitle)])
    document.build(story)
    output.seek(0)
    return output


def save_invoice(order_id, document):
    invoice_directory = Path(__file__).resolve().parents[1] / "invoices"
    invoice_directory.mkdir(parents=True, exist_ok=True)
    invoice_path = invoice_directory / f"ProductiveReads-Invoice-{order_id}.pdf"
    invoice_path.write_bytes(document.getvalue())
    return invoice_path
