import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Set a long random secret before starting Carvion Motors."
        )

    WTF_CSRF_TIME_LIMIT = 7200

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(BASE_DIR, "carvion.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        "static",
        "uploads"
    )

    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        "jpg",
        "jpeg",
        "png",
        "webp"
    }

    REQUIRED_CAR_IMAGES = 5

    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
