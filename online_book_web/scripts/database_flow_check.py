import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db


def main():
    client = app.test_client()
    email = "database.check@example.com"
    with app.app_context():
        database = get_db()
        user = database.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user is None:
            database.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, datetime('now'))", ("Database Check", email, "test-hash"))
            database.commit()
            user = database.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        user_id = user["id"]
        database.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        database.execute("DELETE FROM wishlist WHERE user_id = ?", (user_id,))
        database.commit()

    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = "Database Check"

    client.post("/cart/add/1", data={"quantity": 1})
    client.post("/cart/add/1", data={"quantity": 1})
    with app.app_context():
        database = get_db()
        cart_row = database.execute("SELECT quantity FROM cart WHERE user_id = ? AND book_id = 1", (user_id,)).fetchone()
        if cart_row is None or cart_row["quantity"] != 2:
            raise SystemExit("cart duplicate merge failed")
        database.execute("INSERT OR IGNORE INTO wishlist (user_id, book_id) VALUES (?, ?)", (user_id, 1))
        database.execute("INSERT OR IGNORE INTO wishlist (user_id, book_id) VALUES (?, ?)", (user_id, 1))
        wishlist_count = database.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = ? AND book_id = 1", (user_id,)).fetchone()[0]
        if wishlist_count != 1:
            raise SystemExit("wishlist uniqueness failed")
        print("cart_duplicate_merge=passed")
        print("wishlist_uniqueness=passed")
        print("foreign_key_check=", database.execute("PRAGMA foreign_key_check").fetchall())
        database.execute("DELETE FROM users WHERE id = ?", (user_id,))
        database.commit()


if __name__ == "__main__":
    main()
