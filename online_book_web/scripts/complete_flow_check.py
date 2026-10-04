import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db

EMAIL = "complete.flow.check@example.com"
PASSWORD = "secret123"


def assert_status(response, expected, label):
    if response.status_code != expected:
        raise AssertionError(f"{label}: expected {expected}, got {response.status_code}")


def cleanup_user(database):
    user = database.execute("SELECT id FROM users WHERE email = ?", (EMAIL,)).fetchone()
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
        cleanup_user(database)
        database.commit()

    results = []
    home = client.get("/")
    assert_status(home, 200, "Home")
    results.append("Home: PASS")
    books = client.get("/books")
    assert_status(books, 200, "Books")
    results.append("Books: PASS")
    search = client.get("/books?q=Atomic")
    assert_status(search, 200, "Search")
    assert b"Atomic Habits" in search.data
    results.append("Search: PASS")
    category = client.get("/books?category=habits")
    assert_status(category, 200, "Category filter")
    assert b"Atomic Habits" in category.data
    results.append("Category filter: PASS")
    details = client.get("/book/1")
    assert_status(details, 200, "Book details")
    results.append("Book details: PASS")
    assert_status(client.get("/cart"), 302, "Protected cart")
    results.append("Login protection: PASS")
    invalid = client.post("/login", data={"email": EMAIL, "password": "wrong"})
    assert_status(invalid, 200, "Invalid login")
    assert b"Invalid email or password" in invalid.data
    results.append("Invalid login: PASS")
    register = client.post("/register", data={"name": "Complete Flow Reader", "email": EMAIL, "password": PASSWORD}, follow_redirects=True)
    assert_status(register, 200, "Registration")
    results.append("Registration: PASS")
    client.get("/logout")
    assert_status(client.get("/cart"), 302, "Logout")
    results.append("Logout: PASS")
    login = client.post("/login", data={"email": EMAIL, "password": PASSWORD}, follow_redirects=True)
    assert_status(login, 200, "Login")
    results.append("Login: PASS")

    added = client.post("/cart/add/1", data={"quantity": "1"}, follow_redirects=True)
    assert_status(added, 200, "Add to cart")
    client.post("/cart/add/1", data={"quantity": "1"})
    with app.app_context():
        database = get_db()
        user_id = database.execute("SELECT id FROM users WHERE email = ?", (EMAIL,)).fetchone()["id"]
        cart_item = database.execute("SELECT id, quantity FROM cart WHERE user_id = ? AND book_id = 1", (user_id,)).fetchone()
    assert cart_item["quantity"] == 2
    results.append("Cart quantity increase/merge: PASS")
    client.post(f"/cart/update/{cart_item['id']}", data={"quantity": "1"})
    results.append("Cart quantity decrease: PASS")
    cart_page = client.get("/cart")
    assert_status(cart_page, 200, "Cart")
    assert b"Atomic Habits" in cart_page.data
    wishlist = client.post("/wishlist/toggle/1", data={"next": "/book/1"}, follow_redirects=True)
    assert_status(wishlist, 200, "Wishlist add")
    assert b"Saved to your wishlist" in wishlist.data
    results.append("Wishlist: PASS")
    client.post(f"/cart/remove/{cart_item['id']}")
    assert_status(client.get("/cart"), 200, "Remove item")
    results.append("Remove item: PASS")
    client.post("/cart/add/1", data={"quantity": "1"})
    checkout = client.post("/checkout", data={"customer_name": "Complete Flow Reader", "email": EMAIL, "phone": "9876543210", "address": "Test Street", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001"}, follow_redirects=False)
    assert_status(checkout, 302, "Checkout")
    order_id = int(checkout.location.rstrip("/").split("/")[-1])
    results.append("Checkout and customer details: PASS")
    create_order = client.post("/create-order", json={"order_id": order_id})
    assert_status(create_order, 200, "Create Razorpay order")
    results.append("Razorpay test order: PASS")
    bad_verify = client.post("/verify-payment", json={"order_id": order_id, "razorpay_order_id": "wrong", "razorpay_payment_id": "bad", "razorpay_signature": "bad", "demo_confirmed": "true"})
    assert_status(bad_verify, 400, "Invalid payment")
    with app.app_context():
        assert get_db().execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,)).fetchone()["payment_status"] == "PENDING"
    results.append("Server-side rejection of invalid payment: PASS")
    valid_verify = client.post("/verify-payment", json={"order_id": order_id, "razorpay_order_id": f"demo_order_{order_id}", "razorpay_payment_id": f"demo_payment_{order_id}", "razorpay_signature": "demo_signature", "demo_confirmed": "true"})
    assert_status(valid_verify, 200, "Valid payment")
    with app.app_context():
        database = get_db()
        assert database.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,)).fetchone()["payment_status"] == "PAID"
        assert database.execute("SELECT status FROM payments WHERE order_id = ?", (order_id,)).fetchone()["status"] == "PAID"
        assert database.execute("SELECT COUNT(*) FROM cart WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
    results.append("Payment verification, PAID order, payment record, empty cart: PASS")
    invoice = client.get(f"/orders/{order_id}/invoice")
    assert_status(invoice, 200, "Download invoice")
    assert invoice.data[:4] == b"%PDF"
    assert_status(client.get(f"/orders/{order_id}/invoice/view"), 200, "View invoice")
    assert_status(client.get("/orders"), 200, "Order history")
    results.append("Invoice and order history: PASS")

    client.get("/logout")
    with app.app_context():
        cleanup_user(get_db())
        get_db().commit()
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
