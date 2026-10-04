import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from models.db import get_db, init_db


if __name__ == "__main__":
    with app.app_context():
        init_db()
        database = get_db()
        counts = {}
        for table in ("users", "admins", "categories", "books", "cart", "wishlist", "orders", "order_items", "payments"):
            counts[table] = database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print("Database initialized and seeded.")
        for table, count in counts.items():
            print(f"{table}: {count}")
