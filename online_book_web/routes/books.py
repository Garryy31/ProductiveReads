from flask import Blueprint, abort, render_template

from models.db import get_db

books_bp = Blueprint("books", __name__)


@books_bp.route("/book/<int:book_id>")
def detail(book_id):
    database = get_db()
    book = database.execute(
        """SELECT books.*, categories.name AS category_name, categories.slug AS category_slug
           FROM books JOIN categories ON categories.id = books.category_id
           WHERE books.id = ?""", (book_id,)
    ).fetchone()
    if book is None:
        abort(404)
    related = database.execute(
        """SELECT books.*, categories.name AS category_name
           FROM books JOIN categories ON categories.id = books.category_id
           WHERE books.category_id = ? AND books.id != ?
           ORDER BY books.popularity DESC LIMIT 4""", (book["category_id"], book_id)
    ).fetchall()
    return render_template("book_details.html", book=book, related=related)
