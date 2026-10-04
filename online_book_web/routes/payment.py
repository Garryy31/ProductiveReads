import os
import tempfile
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from models.db import get_db
from utils.helpers import login_required
from utils.invoice import build_invoice, save_invoice

payment_bp = Blueprint("payment", __name__)


def _order_for_user(order_id):
    return get_db().execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, request_user_id())).fetchone()


def request_user_id():
    return session["user_id"]


def has_real_razorpay_keys(key_id, key_secret):
    key_id = (key_id or "").strip()
    key_secret = (key_secret or "").strip()
    if not key_id or not key_secret:
        return False
    lowered_key_id = key_id.lower()
    lowered_key_secret = key_secret.lower()
    if any(marker in lowered_key_id for marker in ("replace-with", "your_key_id", "rzp_test_your_key_id", "example", "demo")):
        return False
    if any(marker in lowered_key_secret for marker in ("replace-with", "your_key_secret", "your_test_key_secret", "example", "demo")):
        return False
    return key_id.startswith("rzp_") and len(key_secret) >= 8


def _keys_configured():
    return has_real_razorpay_keys(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"])


RAZORPAY_TIMEOUT_SECONDS = 20
_ca_bundle_path = None


def _ca_bundle():
    """Razorpay's bundled ca-bundle.crt is a 2015 snapshot and lacks newer root CAs, while
    certifi lacks some older ones. Verify against both so HTTPS to api.razorpay.com works
    whichever chain the server uses. Falls back to the SDK default if anything goes wrong."""
    global _ca_bundle_path
    if _ca_bundle_path and os.path.exists(_ca_bundle_path):
        return _ca_bundle_path
    try:
        import certifi
        import razorpay

        sdk_bundle = os.path.join(os.path.dirname(razorpay.__file__), "ca-bundle.crt")
        parts = []
        for path in (certifi.where(), sdk_bundle):
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    parts.append(handle.read().strip())
        if not parts:
            return None
        merged = os.path.join(tempfile.gettempdir(), "productivereads-razorpay-ca.pem")
        with open(merged, "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(parts) + "\n")
        _ca_bundle_path = merged
        return merged
    except Exception:
        current_app.logger.exception("Could not build merged CA bundle; using Razorpay SDK default")
        return None


def _razorpay_client():
    import razorpay

    client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]))
    bundle = _ca_bundle()
    if bundle:
        client.cert_path = bundle
    return client


def _create_razorpay_order(order):
    if not _keys_configured():
        return f"demo_order_{order['id']}"
    try:
        client = _razorpay_client()
        created_order = client.order.create({
            "amount": int(round(order["total_amount"] * 100)),
            "currency": "INR",
            "receipt": f"pr_{order['id']}",
        }, timeout=RAZORPAY_TIMEOUT_SECONDS)
        return created_order["id"]
    except Exception:
        current_app.logger.warning("Razorpay authentication failed; falling back to demo payment mode.", exc_info=True)
        return f"demo_order_{order['id']}"


def _store_razorpay_order(order):
    database = get_db()
    razorpay_order_id = _create_razorpay_order(order)
    database.execute("UPDATE orders SET razorpay_order_id = ? WHERE id = ?", (razorpay_order_id, order["id"]))
    database.commit()
    return _order_for_user(order["id"])


@payment_bp.post("/create-order")
@login_required
def create_order():
    request_data = request.get_json(silent=True) if request.is_json else request.form
    order_id = request_data.get("order_id") if request_data else None
    order = _order_for_user(order_id) if order_id else None
    if order is None or order["payment_status"] != "PENDING":
        return jsonify({"ok": False, "message": "A pending order is required."}), 404
    try:
        # With real keys always create a fresh Razorpay order: a stored id may be a demo_ id or
        # belong to a different key/account, which makes Checkout fail.
        existing_order_id = order["razorpay_order_id"] or ""
        if not existing_order_id or _keys_configured() or not existing_order_id.startswith("demo_"):
            order = _store_razorpay_order(order)
        return jsonify({"ok": True, "key_id": current_app.config["RAZORPAY_KEY_ID"], "order_id": order["razorpay_order_id"], "amount": int(round(order["total_amount"] * 100)), "currency": "INR"})
    except Exception as error:
        current_app.logger.exception("Unable to create Razorpay order")
        reason = str(error).strip() or error.__class__.__name__
        return jsonify({"ok": False, "message": f"Unable to create the payment order: {reason}"}), 502


@payment_bp.route("/payment/<int:order_id>")
@login_required
def pay(order_id):
    database = get_db()
    order = _order_for_user(order_id)
    if order is None or order["payment_status"] == "PAID":
        return redirect(url_for("checkout.checkout"))
    items = database.execute("SELECT order_items.*, books.title, books.author FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order_id,)).fetchall()
    demo_mode = not _keys_configured()
    return render_template("payment.html", order=order, items=items, demo_mode=demo_mode, razorpay_key=current_app.config["RAZORPAY_KEY_ID"])


@payment_bp.post("/verify-payment")
@login_required
def verify_payment():
    payload = request.get_json(silent=True) or request.form
    order_id = payload.get("order_id")
    order = _order_for_user(order_id) if order_id else None
    if order is None:
        return jsonify({"ok": False, "message": "Order not found."}), 404
    if order["payment_status"] == "PAID":
        if not request.is_json:
            return redirect(url_for("payment.success", order_id=order["id"]))
        return jsonify({"ok": True, "redirect": url_for("payment.success", order_id=order["id"])})
    payment_id = payload.get("razorpay_payment_id", "")
    signature = payload.get("razorpay_signature", "")
    razorpay_order_id = payload.get("razorpay_order_id", "")
    if not payment_id or not razorpay_order_id or not signature or razorpay_order_id != order["razorpay_order_id"]:
        return jsonify({"ok": False, "message": "Incomplete or mismatched payment details."}), 400
    is_demo = order["razorpay_order_id"].startswith("demo_") and not _keys_configured()
    try:
        if is_demo:
            verified = payload.get("demo_confirmed") == "true"
        else:
            client = _razorpay_client()
            client.utility.verify_payment_signature({"razorpay_order_id": razorpay_order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature})
            verified = True
    except Exception:
        current_app.logger.exception("Razorpay payment verification failed for order %s", order["id"])
        verified = False
    if not verified:
        if not request.is_json:
            return redirect(url_for("payment.failure", order_id=order["id"]))
        return jsonify({"ok": False, "message": "Payment verification failed."}), 400
    database = get_db()
    try:
        database.execute("UPDATE orders SET payment_status = 'PAID', razorpay_order_id = ?, razorpay_payment_id = ?, razorpay_signature = ? WHERE id = ?", (razorpay_order_id, payment_id, signature, order["id"]))
        database.execute("INSERT OR IGNORE INTO payments (order_id, razorpay_order_id, razorpay_payment_id, razorpay_signature, amount, status, created_at) VALUES (?, ?, ?, ?, ?, 'PAID', ?)", (order["id"], razorpay_order_id, payment_id, signature, order["total_amount"], datetime.now(timezone.utc).isoformat()))
        database.execute("DELETE FROM cart WHERE user_id = ?", (request_user_id(),))
        database.commit()
    except Exception:
        database.rollback()
        current_app.logger.exception("Unable to finalize verified payment")
        return jsonify({"ok": False, "message": "Payment was verified, but the order could not be finalized."}), 500
    try:
        # The invoice is a bonus: it is rebuilt on demand from the order, so a failure here
        # must never turn an already-verified payment into a failed one.
        paid_order = _order_for_user(order["id"])
        invoice_items = database.execute("SELECT order_items.*, books.title, books.author, books.original_price FROM order_items JOIN books ON books.id = order_items.book_id WHERE order_id = ?", (order["id"],)).fetchall()
        save_invoice(order["id"], build_invoice(paid_order, invoice_items))
    except Exception:
        current_app.logger.exception("Payment saved, but invoice generation failed for order %s", order["id"])
    if not request.is_json:
        return redirect(url_for("payment.success", order_id=order["id"]))
    return jsonify({"ok": True, "redirect": url_for("payment.success", order_id=order["id"])})


@payment_bp.get("/payment-success/<int:order_id>")
@login_required
def success(order_id):
    order = _order_for_user(order_id)
    if order is None or order["payment_status"] != "PAID":
        return redirect(url_for("payment.failure", order_id=order_id))
    return render_template("payment_success.html", order=order)


@payment_bp.get("/payment-failure/<int:order_id>")
@login_required
def failure(order_id):
    order = _order_for_user(order_id)
    if order is None:
        return redirect(url_for("checkout.checkout"))
    return render_template("payment_failed.html", order=order)
