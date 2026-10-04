import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# override=True: .env wins over stale Windows/system env vars (e.g. an old RAZORPAY_KEY_ID)
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    DATABASE_PATH = str(BASE_DIR / os.getenv("DATABASE_PATH", "database/database.db"))
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip().strip('"\'')
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip().strip('"\'')
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads" / "books")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
