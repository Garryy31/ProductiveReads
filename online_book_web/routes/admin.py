from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash

from models.db import get_db
from utils.book_images import delete_image, validate_and_save_image
from utils.invoice import build_invoice, invoice_data

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin = get_db().execute("SELECT * FROM admins WHERE email = ?", (request.form.get("email", "").strip().lower(),)).fetchone()
        if admin and check_password_hash(admin["password_hash"], request.form.get("password", "")):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            return redirect(url_for("admin.dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin/login.html")


@admin_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.get("/")
@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    database = get_db()
    stats = {"books": database.execute("SELECT COUNT(*) FROM books").fetchone()[0], "users": database.execute("SELECT COUNT(*) FROM users").fetchone()[0], "orders": database.execute("SELECT COUNT(*) FROM orders").fetchone()[0], "paid": database.execute("SELECT COUNT(*) FROM orders WHERE payment_status = 'PAID'").fetchone()[0], "revenue": database.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = 'PAID'").fetchone()[0]}
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.get("/profile")
@admin_required
def profile():
    admin = get_db().execute("SELECT name, email, created_at FROM admins WHERE id = ?", (session["admin_id"],)).fetchone()
    return render_template("admin/profile.html", admin=admin)


@admin_bp.get("/wishlist")
@admin_required
def wishlist():
    flash("Wishlist management is available from customer accounts.", "success")
    return redirect(url_for("main.books"))


@admin_bp.route("/books", methods=["GET", "POST"])
@admin_required
def books():
    database = get_db()
    if request.method == "POST":
        form = request.form
        image, image_error = validate_and_save_image(request.files.get("image"))
        if image_error:
            flash(image_error, "error")
            return redirect(url_for("admin.books"))
        try:
            database.execute("INSERT INTO books (title, author, description, takeaways, category_id, price, original_price, rating, popularity, stock, cover_color, image, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (form["title"], form["author"], form["description"], form["takeaways"], form["category_id"], float(form["price"]), float(form["original_price"]), float(form.get("rating", 4.5)), int(form.get("popularity", 0)), int(form.get("stock", 10)), form.get("cover_color", "#dbeafe"), image, datetime.now(timezone.utc).isoformat()))
        except (KeyError, TypeError, ValueError):
            delete_image(image)
            flash("Enter valid book details before saving.", "error")
            return redirect(url_for("admin.books"))
        database.commit()
        flash("Book added successfully.", "success")
        return redirect(url_for("admin.books"))
    search = request.args.get("q", "").strip()
    books_query = """SELECT books.*, categories.name AS category_name
                     FROM books JOIN categories ON categories.id = books.category_id"""
    values = []
    if search:
        books_query += " WHERE books.title LIKE ? OR books.author LIKE ?"
        values.extend([f"%{search}%", f"%{search}%"])
    books_query += " ORDER BY books.id DESC"
    return render_template("admin/books.html", books=database.execute(books_query, values).fetchall(), categories=database.execute("SELECT * FROM categories ORDER BY name").fetchall(), search=search)


@admin_bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_book(book_id):
    database = get_db()
    book = database.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return redirect(url_for("admin.books"))
    if request.method == "POST":
        form = request.form
        try:
            price = float(form["price"])
            original_price = float(form["original_price"])
            stock = int(form["stock"])
            rating = float(form.get("rating", 4.5))
            if price < 0 or original_price < price or stock < 0 or not 0 <= rating <= 5:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            flash("Enter valid price, stock, and rating values.", "error")
            return render_template("admin/edit_book.html", book=book, categories=database.execute("SELECT * FROM categories ORDER BY name").fetchall())
        image, image_error = validate_and_save_image(request.files.get("image"))
        if image_error:
            flash(image_error, "error")
            return render_template("admin/edit_book.html", book=book, categories=database.execute("SELECT * FROM categories ORDER BY name").fetchall())
        database.execute("""UPDATE books SET title = ?, author = ?, description = ?, takeaways = ?,
                         category_id = ?, price = ?, original_price = ?, rating = ?, stock = ?, cover_color = ?, image = COALESCE(?, image)
                         WHERE id = ?""", (form["title"], form["author"], form["description"], form["takeaways"], form["category_id"], price, original_price, rating, stock, form.get("cover_color", book["cover_color"]), image, book_id))
        database.commit()
        if image and book["image"] and book["image"] != image:
            remaining = database.execute("SELECT COUNT(*) FROM books WHERE image = ?", (book["image"],)).fetchone()[0]
            if remaining == 0:
                delete_image(book["image"])
        flash("Book updated.", "success")
        return redirect(url_for("admin.books"))
    return render_template("admin/edit_book.html", book=book, categories=database.execute("SELECT * FROM categories ORDER BY name").fetchall())


@admin_bp.post("/books/<int:book_id>/delete")
@admin_required
def delete_book(book_id):
    database = get_db()
    order_usage = database.execute("SELECT COUNT(*) FROM order_items WHERE book_id = ?", (book_id,)).fetchone()[0]
    if order_usage:
        flash("A book already used in an order cannot be deleted.", "error")
        return redirect(url_for("admin.books"))
    book = database.execute("SELECT image FROM books WHERE id = ?", (book_id,)).fetchone()
    database.execute("DELETE FROM books WHERE id = ?", (book_id,))
    database.commit()
    still_used = database.execute("SELECT COUNT(*) FROM books WHERE image = ?", (book["image"],)).fetchone()[0] if book and book["image"] else 0
    if book and book["image"] and still_used == 0:
        delete_image(book["image"])
    flash("Book deleted.", "success")
    return redirect(url_for("admin.books"))


@admin_bp.app_errorhandler(413)
def upload_too_large(_error):
    flash("Book cover images must be 5 MB or smaller.", "error")
    return redirect(url_for("admin.books"))


@admin_bp.get("/users")
@admin_required
def users():
    search = request.args.get("q", "").strip()
    query = "SELECT id, name, email, created_at FROM users"
    values = []
    if search:
        query += " WHERE name LIKE ? OR email LIKE ?"
        values.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC"
    return render_template("admin/users.html", users=get_db().execute(query, values).fetchall(), search=search)


@admin_bp.route("/orders", methods=["GET", "POST"])
@admin_required
def orders():
    database = get_db()
    search = request.args.get("q", "").strip()
    if request.method == "POST":
        status = request.form.get("payment_status", "PENDING")
        order = database.execute("SELECT payment_status FROM orders WHERE id = ?", (request.form.get("order_id"),)).fetchone()
        if status in {"PENDING", "FAILED", "CANCELLED"} and order is not None and order["payment_status"] != "PAID":
            database.execute("UPDATE orders SET payment_status = ? WHERE id = ?", (status, request.form["order_id"]))
            database.commit()
        return redirect(url_for("admin.orders"))
    query = "SELECT * FROM orders"
    values = []
    if search:
        query += " WHERE CAST(id AS TEXT) LIKE ? OR customer_name LIKE ? OR email LIKE ?"
        values.extend([f"%{search}%"] * 3)
    query += " ORDER BY id DESC"
    return render_template("admin/orders.html", orders=database.execute(query, values).fetchall(), search=search)


@admin_bp.get("/payments")
@admin_required
def payments():
    search = request.args.get("q", "").strip()
    query = "SELECT * FROM payments"
    values = []
    if search:
        query += " WHERE CAST(order_id AS TEXT) LIKE ? OR razorpay_payment_id LIKE ? OR status LIKE ?"
        values.extend([f"%{search}%"] * 3)
    query += " ORDER BY id DESC"
    return render_template("admin/payments.html", payments=get_db().execute(query, values).fetchall(), search=search)


@admin_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    database = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = name.lower().replace(" ", "-")
        if name:
            database.execute("INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)", (name, slug))
            database.commit()
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", categories=database.execute("SELECT categories.*, COUNT(books.id) AS book_count FROM categories LEFT JOIN books ON books.category_id = categories.id GROUP BY categories.id ORDER BY categories.name").fetchall())


@admin_bp.post("/categories/<int:category_id>/delete")
@admin_required
def delete_category(category_id):
    database = get_db()
    book_count = database.execute("SELECT COUNT(*) FROM books WHERE category_id = ?", (category_id,)).fetchone()[0]
    if book_count == 0:
        database.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        database.commit()
    else:
        flash("A category with books cannot be deleted.", "error")
    return redirect(url_for("admin.categories"))


@admin_bp.get("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    database = get_db()
    order = database.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        return redirect(url_for("admin.orders"))
    items = database.execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("admin/order_detail.html", order=order, items=items)


@admin_bp.get("/orders/<int:order_id>/invoice")
@admin_required
def order_invoice(order_id):
    database = get_db()
    order = database.execute("SELECT * FROM orders WHERE id = ? AND payment_status = 'PAID'", (order_id,)).fetchone()
    if order is None:
        return redirect(url_for("admin.orders"))
    items = database.execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return send_file(build_invoice(order, items), mimetype="application/pdf", as_attachment=True, download_name=f"ProductiveReads-Invoice-{order_id}.pdf")


@admin_bp.get("/orders/<int:order_id>/invoice/view")
@admin_required
def order_invoice_view(order_id):
    database = get_db()
    order = database.execute("SELECT * FROM orders WHERE id = ? AND payment_status = 'PAID'", (order_id,)).fetchone()
    if order is None:
        return redirect(url_for("admin.orders"))
    items = database.execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("invoice.html", order=order, invoice=invoice_data(order, items), is_admin=True)
