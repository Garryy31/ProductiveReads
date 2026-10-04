import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db


def main():
    with app.app_context():
        database = get_db()
        paid = database.execute("SELECT id, user_id FROM orders WHERE payment_status = 'PAID' ORDER BY id DESC LIMIT 1").fetchone()
        pending = database.execute("SELECT id FROM orders WHERE payment_status = 'PENDING' ORDER BY id DESC LIMIT 1").fetchone()
    if paid is None:
        raise SystemExit("No paid order exists for invoice validation")

    client = app.test_client()
    client.post("/admin/login", data={"email": "admin@productivereads.local", "password": "admin123"})
    admin_view = client.get(f"/admin/orders/{paid['id']}/invoice/view")
    admin_pdf = client.get(f"/admin/orders/{paid['id']}/invoice")
    admin_pending = client.get(f"/admin/orders/{pending['id']}/invoice") if pending else None

    with client.session_transaction() as session:
        session["user_id"] = paid["user_id"]
        session["user_name"] = "Invoice Reader"
    user_view = client.get(f"/orders/{paid['id']}/invoice/view")
    user_pdf = client.get(f"/orders/{paid['id']}/invoice")
    view_text = user_view.get_data(as_text=True)

    print(f"admin_view={admin_view.status_code}")
    print(f"admin_pdf={admin_pdf.status_code} pdf_header={admin_pdf.data[:4] == b'%PDF'}")
    print(f"admin_pending={admin_pending.status_code if admin_pending else 'none'}")
    print(f"user_view={user_view.status_code} user_pdf={user_pdf.status_code}")
    print(f"invoice_totals={all(value in view_text for value in ('Subtotal', 'Discount', 'Tax', 'Grand Total'))}")
    if admin_view.status_code != 200 or admin_pdf.status_code != 200 or admin_pdf.data[:4] != b"%PDF" or (admin_pending and admin_pending.status_code != 302) or user_view.status_code != 200 or user_pdf.status_code != 200 or not all(value in view_text for value in ("Subtotal", "Discount", "Tax", "Grand Total")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
