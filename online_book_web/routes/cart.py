from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.db import get_db
from utils.helpers import login_required

cart_bp = Blueprint("cart", __name__)


def _requested_quantity(value, default=1):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _cart_rows():
    return get_db().execute(
        """SELECT cart.id AS cart_id, cart.quantity, books.*, categories.name AS category_name
           FROM cart JOIN books ON books.id = cart.book_id
           JOIN categories ON categories.id = books.category_id
           WHERE cart.user_id = ? ORDER BY cart.id DESC""", (session["user_id"],)
    ).fetchall()


def _totals(items):
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    original_total = sum(item["original_price"] * item["quantity"] for item in items)
    return {"subtotal": subtotal, "discount": original_total - subtotal, "total": subtotal}


@cart_bp.route("/cart")
@login_required
def view_cart():
    items = _cart_rows()
    return render_template("cart.html", items=items, totals=_totals(items))


@cart_bp.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def add_to_cart(book_id):
    database = get_db()
    book = database.execute("SELECT id, stock FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        flash("That book is no longer available.", "error")
        return redirect(url_for("main.books"))
    requested_quantity = max(1, _requested_quantity(request.form.get("quantity", 1)))
    existing = database.execute("SELECT quantity FROM cart WHERE user_id = ? AND book_id = ?", (session["user_id"], book_id)).fetchone()
    new_quantity = requested_quantity + (existing["quantity"] if existing else 0)
    if new_quantity > book["stock"]:
        flash(f"Only {book['stock']} copies are available.", "error")
        return redirect(request.referrer or url_for("main.books"))
    if existing:
        database.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND book_id = ?", (new_quantity, session["user_id"], book_id))
    else:
        database.execute("INSERT INTO cart (user_id, book_id, quantity) VALUES (?, ?, ?)", (session["user_id"], book_id, requested_quantity))
    database.commit()
    flash("Added to your cart.", "success")
    return redirect(request.form.get("next") or request.referrer or url_for("cart.view_cart"))


@cart_bp.route("/cart/update/<int:cart_id>", methods=["POST"])
@login_required
def update_cart(cart_id):
    database = get_db()
    quantity = min(99, _requested_quantity(request.form.get("quantity", 1)))
    item = database.execute(
        """SELECT cart.book_id, books.stock FROM cart JOIN books ON books.id = cart.book_id
           WHERE cart.id = ? AND cart.user_id = ?""", (cart_id, session["user_id"])
    ).fetchone()
    if item is None:
        return redirect(url_for("cart.view_cart"))
    if quantity == 0:
        database.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
    else:
        available_quantity = min(quantity, item["stock"])
        if available_quantity == 0:
            database.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        else:
            database.execute("UPDATE cart SET quantity = ? WHERE id = ?", (available_quantity, cart_id))
    database.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/cart/remove/<int:cart_id>", methods=["POST"])
@login_required
def remove_from_cart(cart_id):
    database = get_db()
    database.execute("DELETE FROM cart WHERE id = ? AND user_id = ?", (cart_id, session["user_id"]))
    database.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/wishlist")
@login_required
def wishlist():
    items = get_db().execute(
        """SELECT books.*, categories.name AS category_name FROM wishlist
           JOIN books ON books.id = wishlist.book_id JOIN categories ON categories.id = books.category_id
           WHERE wishlist.user_id = ? ORDER BY wishlist.id DESC""", (session["user_id"],)
    ).fetchall()
    return render_template("wishlist.html", items=items)


@cart_bp.route("/wishlist/toggle/<int:book_id>", methods=["POST"])
@login_required
def toggle_wishlist(book_id):
    database = get_db()
    existing = database.execute("SELECT id FROM wishlist WHERE user_id = ? AND book_id = ?", (session["user_id"], book_id)).fetchone()
    if existing:
        database.execute("DELETE FROM wishlist WHERE id = ?", (existing["id"],))
        flash("Removed from your wishlist.", "success")
    else:
        database.execute("INSERT OR IGNORE INTO wishlist (user_id, book_id) VALUES (?, ?)", (session["user_id"], book_id))
        flash("Saved to your wishlist.", "success")
    database.commit()
    return redirect(request.form.get("next") or request.referrer or url_for("cart.wishlist"))


@cart_bp.route("/wishlist/remove/<int:book_id>", methods=["POST"])
@login_required
def remove_from_wishlist(book_id):
    database = get_db()
    database.execute("DELETE FROM wishlist WHERE user_id = ? AND book_id = ?", (session["user_id"], book_id))
    database.commit()
    return redirect(url_for("cart.wishlist"))


@cart_bp.route("/profile")
@login_required
def profile():
    user = get_db().execute("SELECT id, name, email, phone, created_at FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("profile.html", user=user)
