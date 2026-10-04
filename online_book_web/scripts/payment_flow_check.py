from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db

EMAIL = "payment.flow.check@example.com"


def remove_test_user(database, email):
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
    client = app.test_client()
    with app.app_context():
        database = get_db()
        remove_test_user(database, EMAIL)
        database.commit()
        database.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, datetime('now'))", ("Payment Flow Check", EMAIL, "test-hash"))
        user_id = database.execute("SELECT id FROM users WHERE email = ?", (EMAIL,)).fetchone()["id"]
        database.commit()

    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = "Payment Flow Check"

    client.post("/cart/add/1", data={"quantity": 1})
    checkout = client.post("/checkout", data={"customer_name": "Payment Flow Check", "email": EMAIL, "phone": "9876543210", "address": "Test Street", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001"}, follow_redirects=False)
    order_id = int(checkout.location.rstrip("/").split("/")[-1])
    created = client.post("/create-order", json={"order_id": order_id})
    invalid = client.post("/verify-payment", json={"order_id": order_id, "razorpay_order_id": "wrong", "razorpay_payment_id": "invalid", "razorpay_signature": "invalid", "demo_confirmed": "true"})

    with app.app_context():
        pending = get_db().execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,)).fetchone()["payment_status"]

    valid = client.post("/verify-payment", json={"order_id": order_id, "razorpay_order_id": f"demo_order_{order_id}", "razorpay_payment_id": f"demo_payment_{order_id}", "razorpay_signature": "demo_signature", "demo_confirmed": "true"})
    with app.app_context():
        database = get_db()
        paid = database.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,)).fetchone()["payment_status"]
        payment = database.execute("SELECT status FROM payments WHERE order_id = ?", (order_id,)).fetchone()["status"]
        remove_test_user(database, EMAIL)
        database.commit()

    invoice_exists = (ROOT / "invoices" / f"ProductiveReads-Invoice-{order_id}.pdf").exists()
    print(f"create_order={created.status_code}")
    print(f"invalid_verification={invalid.status_code} pending_status={pending}")
    print(f"valid_verification={valid.status_code} order_status={paid} payment_status={payment}")
    print(f"invoice_generated={invoice_exists}")
    if created.status_code != 200 or invalid.status_code != 400 or pending != "PENDING" or valid.status_code != 200 or paid != "PAID" or payment != "PAID" or not invoice_exists:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
