import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE_PATH"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    database = get_db()
    database.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            phone TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            description TEXT NOT NULL,
            takeaways TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            original_price REAL NOT NULL CHECK(original_price >= price),
            rating REAL NOT NULL DEFAULT 4.5 CHECK(rating BETWEEN 0 AND 5),
            popularity INTEGER NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 10 CHECK(stock >= 0),
            cover_color TEXT NOT NULL DEFAULT '#dbeafe',
            image TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            UNIQUE(user_id, book_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            UNIQUE(user_id, book_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            pincode TEXT NOT NULL DEFAULT '',
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Razorpay',
            payment_status TEXT NOT NULL DEFAULT 'PENDING',
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            razorpay_signature TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            price REAL NOT NULL CHECK(price >= 0),
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(book_id) REFERENCES books(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            razorpay_signature TEXT,
            amount REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING', 'PAID', 'FAILED', 'CANCELLED')),
            created_at TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """
    )
    existing_order_columns = {row["name"] for row in database.execute("PRAGMA table_info(orders)").fetchall()}
    for column in ("city", "state", "pincode"):
        if column not in existing_order_columns:
            database.execute(f"ALTER TABLE orders ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    existing_book_columns = {row["name"] for row in database.execute("PRAGMA table_info(books)").fetchall()}
    if "image" not in existing_book_columns:
        database.execute("ALTER TABLE books ADD COLUMN image TEXT")
    database.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_order_items_order_book ON order_items(order_id, book_id)")
    database.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_order ON payments(order_id)")
    database.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_razorpay_id ON payments(razorpay_payment_id) WHERE razorpay_payment_id IS NOT NULL")

    category_names = [
        "Productivity", "Self Growth", "Motivation", "Personal Development",
        "Psychology", "Finance", "Career", "Leadership", "Habits",
        "Communication", "Time Management", "Entrepreneurship",
    ]
    for name in category_names:
        slug = name.lower().replace(" ", "-")
        database.execute("INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)", (name, slug))

    books = [
        ("Atomic Habits", "James Clear", "A practical guide to building good habits and breaking bad ones through small, consistent changes.", "Identity-based habits; systems over goals; make good habits obvious.", "Habits", 399, 599, 4.9, 980, "#d9f99d"),
        ("Deep Work", "Cal Newport", "Rules for focused success in a distracted world, designed for meaningful and demanding work.", "Focus rituals; attention management; high-quality output.", "Productivity", 449, 699, 4.8, 860, "#bfdbfe"),
        ("The Psychology of Money", "Morgan Housel", "Timeless lessons on wealth, greed, risk, and making better financial decisions.", "Behavior beats spreadsheets; patience; long-term thinking.", "Finance", 499, 799, 4.8, 920, "#fde68a"),
        ("Ikigai", "Hector Garcia", "A gentle exploration of purpose, longevity, and the daily practices that make life meaningful.", "Purpose; balance; daily rituals; community.", "Self Growth", 299, 499, 4.6, 710, "#fecdd3"),
        ("Make Time", "Jake Knapp & John Zeratsky", "Simple strategies to design days around what matters most to you.", "Daily highlight; laser mode; energy management.", "Time Management", 379, 599, 4.7, 640, "#c4b5fd"),
        ("Think and Grow Rich", "Napoleon Hill", "Classic principles for cultivating a purposeful mindset and taking persistent action.", "Definite purpose; organized planning; persistence.", "Motivation", 249, 399, 4.5, 590, "#fed7aa"),
        ("The 7 Habits of Highly Effective People", "Stephen R. Covey", "An enduring framework for personal responsibility, priorities, and effective relationships.", "Be proactive; prioritize; seek mutual benefit.", "Personal Development", 549, 899, 4.8, 810, "#bae6fd"),
        ("How to Win Friends and Influence People", "Dale Carnegie", "Practical ideas for communicating with empathy and building stronger relationships.", "Listen well; appreciate sincerely; disagree respectfully.", "Communication", 329, 499, 4.7, 750, "#a7f3d0"),
        ("The Compound Effect", "Darren Hardy", "How small, smart choices compound into remarkable results over time.", "Consistency; momentum; tracking choices.", "Personal Development", 349, 549, 4.5, 480, "#e9d5ff"),
        ("Eat That Frog!", "Brian Tracy", "A focused approach to defeating procrastination and getting important work done.", "Prioritize; start with the hardest task; plan tomorrow.", "Productivity", 279, 449, 4.4, 530, "#fef08a"),
        ("Rich Dad Poor Dad", "Robert T. Kiyosaki", "A perspective-shifting introduction to financial literacy, assets, and entrepreneurship.", "Financial education; assets; entrepreneurial thinking.", "Finance", 399, 649, 4.6, 880, "#bbf7d0"),
        ("The Power of Now", "Eckhart Tolle", "A reflective guide to presence, awareness, and freedom from unhelpful thought patterns.", "Presence; observing thought; acceptance.", "Psychology", 429, 699, 4.6, 620, "#ddd6fe"),
    ]
    if database.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
        timestamp = datetime.now(timezone.utc).isoformat()
        for book in books:
            category_id = database.execute("SELECT id FROM categories WHERE name = ?", (book[4],)).fetchone()[0]
            database.execute(
                """INSERT INTO books
                (title, author, description, takeaways, category_id, price, original_price,
                 rating, popularity, cover_color, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*book[:4], category_id, *book[5:], timestamp),
            )

    if database.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        database.execute(
            "INSERT INTO admins (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("ProductiveReads Admin", "admin@productivereads.local", generate_password_hash("admin123"), datetime.now(timezone.utc).isoformat()),
        )
    database.commit()
