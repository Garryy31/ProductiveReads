import sqlite3

from flask import Blueprint, render_template, request

from models.db import get_db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    database = get_db()
    featured = database.execute(
        """SELECT books.*, categories.name AS category_name
           FROM books JOIN categories ON categories.id = books.category_id
           ORDER BY rating DESC, popularity DESC LIMIT 4"""
    ).fetchall()
    popular = database.execute(
        """SELECT books.*, categories.name AS category_name
           FROM books JOIN categories ON categories.id = books.category_id
           ORDER BY popularity DESC LIMIT 4"""
    ).fetchall()
    categories = database.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template("index.html", featured=featured, popular=popular, categories=categories)


@main_bp.route("/books")
def books():
    database = get_db()
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "popular")
    filters = []
    values = []
    if query:
        filters.append("(books.title LIKE ? OR books.author LIKE ? OR books.description LIKE ? OR categories.name LIKE ?)")
        values.extend([f"%{query}%"] * 4)
    if category:
        filters.append("categories.slug = ?")
        values.append(category)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    order_by = {
        "price_low": "books.price ASC",
        "price_high": "books.price DESC",
        "newest": "books.created_at DESC",
        "rating": "books.rating DESC",
    }.get(sort, "books.popularity DESC")
    results = database.execute(
        f"""SELECT books.*, categories.name AS category_name
            FROM books JOIN categories ON categories.id = books.category_id
            {where_clause} ORDER BY {order_by}""", values
    ).fetchall()
    categories = database.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template("books.html", books=results, categories=categories, query=query, selected_category=category, selected_sort=sort)


@main_bp.route("/about")
def about():
    return render_template("about.html")


@main_bp.route("/contact")
def contact():
    return render_template("contact.html")


@main_bp.app_errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


@main_bp.app_errorhandler(500)
def server_error(_error):
    return render_template("errors/500.html"), 500
