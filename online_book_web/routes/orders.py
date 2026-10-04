from flask import Blueprint, abort, render_template, send_file, session

from models.db import get_db
from utils.helpers import login_required
from utils.invoice import build_invoice, invoice_data

orders_bp = Blueprint("orders", __name__)


def _order(order_id):
    return get_db().execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"])).fetchone()


@orders_bp.get("/orders")
@login_required
def history():
    orders = get_db().execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("orders.html", orders=orders)


@orders_bp.get("/orders/<int:order_id>")
@login_required
def detail(order_id):
    order = _order(order_id)
    if order is None:
        abort(404)
    items = get_db().execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("order_details.html", order=order, items=items)


@orders_bp.get("/orders/<int:order_id>/invoice")
@login_required
def invoice(order_id):
    order = _order(order_id)
    if order is None or order["payment_status"] != "PAID":
        abort(404)
    items = get_db().execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return send_file(build_invoice(order, items), mimetype="application/pdf", as_attachment=True, download_name=f"ProductiveReads-Invoice-{order_id}.pdf")


@orders_bp.get("/orders/<int:order_id>/invoice/view")
@login_required
def invoice_view(order_id):
    order = _order(order_id)
    if order is None or order["payment_status"] != "PAID":
        abort(404)
    items = get_db().execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("invoice.html", order=order, invoice=invoice_data(order, items), is_admin=False)
