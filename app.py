import importlib.util
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent / "online_book_web"
if not (PROJECT_DIR / "app.py").is_file():
    raise FileNotFoundError(f"Bookstore app was not found at {PROJECT_DIR / 'app.py'}")

sys.path.insert(0, str(PROJECT_DIR))

APP_SPEC = importlib.util.spec_from_file_location("online_book_web_app", PROJECT_DIR / "app.py")
if APP_SPEC is None or APP_SPEC.loader is None:
    raise ImportError(f"Could not load bookstore app from {PROJECT_DIR / 'app.py'}")

BOOKSTORE_APP = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = BOOKSTORE_APP
APP_SPEC.loader.exec_module(BOOKSTORE_APP)


if __name__ == "__main__":
    BOOKSTORE_APP.app.run(debug=True)