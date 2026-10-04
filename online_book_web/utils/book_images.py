from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def validate_and_save_image(upload: FileStorage | None):
    if upload is None or not upload.filename:
        return None, None
    original_name = secure_filename(upload.filename)
    suffix = Path(original_name).suffix.lower().lstrip(".")
    if not original_name or suffix not in ALLOWED_EXTENSIONS or upload.mimetype not in ALLOWED_MIMETYPES:
        return None, "Upload a JPG, JPEG, PNG, or WEBP image."
    upload.stream.seek(0, 2)
    file_size = upload.stream.tell()
    upload.stream.seek(0)
    if file_size > MAX_IMAGE_SIZE:
        return None, "Book cover images must be 5 MB or smaller."
    if Image is not None:
        try:
            with Image.open(upload.stream) as image:
                image.verify()
            upload.stream.seek(0)
        except Exception:
            return None, "The uploaded file is not a valid image."
    filename = f"book_{uuid4().hex}.{suffix}"
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    upload.save(upload_folder / filename)
    return filename, None


def delete_image(filename):
    if not filename:
        return
    image_path = Path(current_app.config["UPLOAD_FOLDER"]) / Path(filename).name
    try:
        image_path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Unable to remove book image: %s", image_path)
