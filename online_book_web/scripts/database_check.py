import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parents[1] / "database" / "database.db"
REQUIRED_TABLES = {"users", "admins", "categories", "books", "cart", "wishlist", "orders", "order_items", "payments"}
REQUIRED_INDEXES = {"uq_order_items_order_book", "uq_payments_order", "uq_payments_razorpay_id"}


def main():
    database = sqlite3.connect(DATABASE_PATH)
    database.execute("PRAGMA foreign_keys = ON")
    tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    missing = REQUIRED_TABLES - tables
    indexes = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    missing_indexes = REQUIRED_INDEXES - indexes
    foreign_key_errors = database.execute("PRAGMA foreign_key_check").fetchall()
    duplicate_checks = {
        "cart": database.execute("SELECT user_id, book_id FROM cart GROUP BY user_id, book_id HAVING COUNT(*) > 1").fetchall(),
        "wishlist": database.execute("SELECT user_id, book_id FROM wishlist GROUP BY user_id, book_id HAVING COUNT(*) > 1").fetchall(),
        "order_items": database.execute("SELECT order_id, book_id FROM order_items GROUP BY order_id, book_id HAVING COUNT(*) > 1").fetchall(),
        "payments": database.execute("SELECT order_id FROM payments GROUP BY order_id HAVING COUNT(*) > 1").fetchall(),
    }
    print(f"database={DATABASE_PATH}")
    print(f"tables={sorted(tables)}")
    print(f"missing_tables={sorted(missing)}")
    print(f"missing_relationship_indexes={sorted(missing_indexes)}")
    print(f"foreign_key_errors={foreign_key_errors}")
    print(f"duplicates={duplicate_checks}")
    database.close()
    if missing or missing_indexes or foreign_key_errors or any(duplicate_checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
