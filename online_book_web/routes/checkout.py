import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.db import get_db
from routes.cart import _cart_rows, _totals
from utils.helpers import login_required

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = _cart_rows()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart.view_cart"))
    if request.method == "POST":
        fields = {key: request.form.get(key, "").strip() for key in ("customer_name", "email", "phone", "address", "city", "state", "pincode")}
        valid_email = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", fields["email"])
        valid_phone = re.fullmatch(r"\d{7,15}", fields["phone"])
        valid_pincode = re.fullmatch(r"\d{5,6}", fields["pincode"])
        if not all(fields.values()) or not valid_email or not valid_phone or not valid_pincode:
            flash("Enter valid name, email, phone, address, city, state, and pincode details.", "error")
            return render_template("checkout.html", items=items, totals=_totals(items), form=fields)
        database = get_db()
        totals = _totals(items)
        cursor = database.execute(
                """INSERT INTO orders (user_id, customer_name, email, phone, address, city, state, pincode, total_amount, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (session["user_id"], fields["customer_name"], fields["email"], fields["phone"], fields["address"], fields["city"], fields["state"], fields["pincode"], totals["total"]),
        )
        order_id = cursor.lastrowid
        for item in items:
            database.execute("INSERT INTO order_items (order_id, book_id, quantity, price) VALUES (?, ?, ?, ?)", (order_id, item["id"], item["quantity"], item["price"]))
        database.commit()
        return redirect(url_for("payment.pay", order_id=order_id))
    user = get_db().execute("SELECT name, email, phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    form = {"customer_name": user["name"], "email": user["email"], "phone": user["phone"] or "", "address": "", "city": "", "state": "", "pincode": ""}
    return render_template("checkout.html", items=items, totals=_totals(items), form=form)
