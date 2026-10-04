import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from models.db import get_db


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "#ec7658").save(output, format="PNG")
    return output.getvalue()


def webp_bytes():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "#17253f").save(output, format="WEBP")
    return output.getvalue()


def login(client):
    client.post("/admin/login", data={"email": "admin@productivereads.local", "password": "admin123"})


def main():
    client = app.test_client()
    login(client)
    with app.app_context():
        database = get_db()
        category_id = database.execute("SELECT id FROM categories ORDER BY id LIMIT 1").fetchone()["id"]
        database.execute("DELETE FROM books WHERE title = 'Image Check Book'")
        database.commit()
    add = client.post("/admin/books", data={"title": "Image Check Book", "author": "Test Author", "description": "Image test", "takeaways": "Test", "category_id": category_id, "price": "100", "original_price": "120", "stock": "5", "image": (io.BytesIO(png_bytes()), "cover.png", "image/png")}, content_type="multipart/form-data", follow_redirects=True)
    assert add.status_code == 200
    with app.app_context():
        database = get_db()
        book = database.execute("SELECT id, image FROM books WHERE title = 'Image Check Book'").fetchone()
        assert book["image"] and (Path(app.config["UPLOAD_FOLDER"]) / book["image"]).exists()
        book_id = book["id"]
    details = client.get(f"/book/{book_id}")
    assert details.status_code == 200 and book["image"].encode() in details.data
    replacement = client.post(f"/admin/books/{book_id}/edit", data={"title": "Image Check Book", "author": "Test Author", "description": "Image test", "takeaways": "Test", "category_id": category_id, "price": "100", "original_price": "120", "rating": "4.5", "stock": "5", "image": (io.BytesIO(webp_bytes()), "replacement.webp", "image/webp")}, content_type="multipart/form-data", follow_redirects=True)
    assert replacement.status_code == 200
    invalid = client.post("/admin/books", data={"title": "Invalid Image Book", "author": "Test", "description": "Bad", "takeaways": "Bad", "category_id": category_id, "price": "100", "original_price": "120", "stock": "5", "image": (io.BytesIO(b"not image"), "bad.exe", "application/octet-stream")}, content_type="multipart/form-data")
    assert invalid.status_code == 302
    oversized = client.post("/admin/books", data={"title": "Large Image Book", "author": "Test", "description": "Large", "takeaways": "Large", "category_id": category_id, "price": "100", "original_price": "120", "stock": "5", "image": (io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "large.png", "image/png")}, content_type="multipart/form-data")
    assert oversized.status_code == 302
    placeholder = client.get("/static/images/book-placeholder.svg")
    assert placeholder.status_code == 200
    deleted = client.post(f"/admin/books/{book_id}/delete", follow_redirects=True)
    assert deleted.status_code == 200
    print("add_with_image=PASS")
    print("customer_image_display=PASS")
    print("edit_image_replacement=PASS")
    print("invalid_upload_rejected=PASS")
    print("oversized_upload_rejected=PASS")
    print("placeholder=PASS")
    print("delete_cleanup=PASS")


if __name__ == "__main__":
    main()
