import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db

USER_A = "security.user.a@example.com"
USER_B = "security.user.b@example.com"


def cleanup(database, email):
    user = database.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if user is None:
        return
    user_id = user["id"]
    order_ids = [row["id"] for row in database.execute("SELECT id FROM orders WHERE user_id = ?", (user_id,)).fetchall()]
    for order_id in order_ids:
        database.execute("DELETE FROM payments WHERE order_id = ?", (order_id,))
        database.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    database.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
    database.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    database.execute("DELETE FROM wishlist WHERE user_id = ?", (user_id,))
    database.execute("DELETE FROM users WHERE id = ?", (user_id,))


def main():
    with app.app_context():
        database = get_db()
        cleanup(database, USER_A)
        cleanup(database, USER_B)
        database.commit()

    client = app.test_client()
    registered = client.post("/register", data={"name": "Security A", "email": USER_A, "password": "secure123"}, follow_redirects=True)
    with app.app_context():
        database = get_db()
        user_a = database.execute("SELECT id, password_hash FROM users WHERE email = ?", (USER_A,)).fetchone()
    assert registered.status_code == 200 and user_a["password_hash"] != "secure123"
    print("password_hashing=PASS")

    client.post("/cart/add/1", data={"quantity": "999"})
    with app.app_context():
        database = get_db()
        oversized = database.execute("SELECT COUNT(*) FROM cart WHERE user_id = ?", (user_a["id"],)).fetchone()[0]
    assert oversized == 0
    print("quantity_limit=PASS")

    client.post("/cart/add/1", data={"quantity": "1"})
    checkout = client.post("/checkout", data={"customer_name": "Security A", "email": USER_A, "phone": "9876543210", "address": "Test", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001", "price": "1"}, follow_redirects=False)
    order_id = int(checkout.location.rstrip("/").split("/")[-1])
    with app.app_context():
        database = get_db()
        order = database.execute("SELECT total_amount FROM orders WHERE id = ?", (order_id,)).fetchone()
        book_price = database.execute("SELECT price FROM books WHERE id = 1").fetchone()["price"]
    assert order["total_amount"] == book_price
    print("server_price_calculation=PASS")

    client.get("/logout")
    client.post("/register", data={"name": "Security B", "email": USER_B, "password": "secure123"}, follow_redirects=True)
    assert client.get(f"/orders/{order_id}").status_code == 404
    assert client.get(f"/orders/{order_id}/invoice").status_code == 404
    print("order_and_invoice_ownership=PASS")
    client.get("/logout")

    client.post("/login", data={"email": USER_A, "password": "secure123"})
    assert client.get("/admin/").status_code == 302
    print("admin_authorization=PASS")
    client.get("/logout")

    client.post("/admin/login", data={"email": "admin@productivereads.local", "password": "admin123"})
    admin_paid_attempt = client.post("/admin/orders", data={"order_id": order_id, "payment_status": "PAID"}, follow_redirects=True)
    with app.app_context():
        status = get_db().execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,)).fetchone()["payment_status"]
    assert admin_paid_attempt.status_code == 200 and status == "PENDING"
    print("admin_cannot_bypass_payment=PASS")

    with app.app_context():
        database = get_db()
        cleanup(database, USER_A)
        cleanup(database, USER_B)
        database.commit()


if __name__ == "__main__":
    main()
