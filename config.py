import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # -------------------------
    # Flask Configuration
    # -------------------------
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "carvion_secret_key_2026"
    )

    # -------------------------
    # Database Configuration
    # -------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "carvion.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # -------------------------
    # Upload Configuration
    # -------------------------
    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        "static",
        "uploads"
    )

    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # -------------------------
    # Allowed Image Types
    # -------------------------
    ALLOWED_EXTENSIONS = {
        "jpg",
        "jpeg",
        "png",
        "webp"
    }

    # -------------------------
    # Car Image Requirements
    # -------------------------
    REQUIRED_CAR_IMAGES = 7

    # -------------------------
    # Session Configuration
    # -------------------------
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"