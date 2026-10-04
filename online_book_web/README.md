# ProductiveReads

ProductiveReads is a Flask and SQLite bookstore for self-growth, productivity, personal development, and career-focused books.

## Phase 1 setup

1. Install Python 3.11 or newer.
2. Open this folder in VS Code and create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set a random `SECRET_KEY`. Razorpay keys can remain blank until the payment phase.
5. Start the server:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

6. Open `http://127.0.0.1:5000`.

The first run creates `database/database.db`, categories, 12 sample books, and the development admin account. The admin panel is available at `http://127.0.0.1:5000/admin/login`:

- Email: `admin@productivereads.local`
- Password: `admin123`

## Razorpay Test Mode

1. Sign in to the Razorpay Dashboard and use **Test Mode**.
2. Copy `.env.example` to `.env` in the project root.
3. Enter the credentials in the project-root `.env` file:

   ```env
   RAZORPAY_KEY_ID=rzp_test_your_key_id
   RAZORPAY_KEY_SECRET=your_test_key_secret
   ```

`RAZORPAY_KEY_ID` is sent to the browser for Checkout. `RAZORPAY_KEY_SECRET` is read only by Flask and is never included in HTML or JavaScript. Restart the Flask server after changing `.env`.

The server creates orders through `/create-order`, converts the server-calculated INR total to paise, and verifies `razorpay_order_id`, `razorpay_payment_id`, and `razorpay_signature` through the Razorpay Python SDK at `/verify-payment`. With blank keys, local demo mode remains available; it does not contact Razorpay.

Database utilities:

```powershell
.\.venv\Scripts\python.exe scripts\init_database.py
.\.venv\Scripts\python.exe scripts\database_check.py
.\.venv\Scripts\python.exe scripts\database_flow_check.py
.\.venv\Scripts\python.exe scripts\payment_flow_check.py
```

The check scripts verify all required tables, foreign-key integrity, relationship uniqueness indexes, duplicate cart/wishlist/order-item/payment rows, cart quantity merging, rejected payment callbacks, successful payment verification, and invoice generation.

## Book cover images

Book covers are stored in `static/uploads/books/` using unique generated filenames. The database stores only the filename in the `books.image` column. Admins can upload a JPG, JPEG, PNG, or WEBP cover up to 5 MB while adding or editing a book. Missing covers use the bundled placeholder at `static/images/book-placeholder.svg`.

To verify image upload, replacement, validation, fallback, and cleanup:

```powershell
.\.venv\Scripts\python.exe scripts\book_image_check.py
```

## Planned phases

Phase 1 provides the catalog, search and filters, authentication, seed data, error pages, and responsive storefront shell. Phase 2 adds book details, authenticated cart operations, wishlist, and profile views. Phase 3 adds checkout, Razorpay test orders with server-side signature verification, and local demo payment mode. Phase 4 adds order history, order details, and ReportLab PDF invoices. Phase 5 adds the protected admin dashboard, catalog creation/editing/deletion, search, user list, order status controls, and payment log.
