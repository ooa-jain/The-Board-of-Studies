"""Configuration for the JAIN Office of Academics Data Portal."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
    MONGO_DB = os.getenv("MONGO_DB", "jain_bos_portal")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ooa.admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeThisOnFirstLogin!")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Office of Academics")

    ACADEMIC_YEAR = os.getenv("ACADEMIC_YEAR", "2027-28")

    UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_MB", "32")) * 1024 * 1024

    PORT = int(os.getenv("PORT", "8102"))
    DEBUG = _bool("FLASK_DEBUG", False)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", not DEBUG)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 10  # 10 hours

    # The campuses as the Office of Academics workbook spells them, and the
    # two cities they sit in.
    PLACES = ["Bangalore", "Kochi"]
    CAMPUSES = [
        "Jain Global Campus", "Jayanagar Campus", "JC Road Campus",
        "JP Nagar Campus", "Lalbagh Campus", "Lalbagh Campus (Jainology)",
        "Sheshadri Road Campus", "Whitefield Campus", "Yelahanka Campus",
        "The Sports School", "Kochi Campus",
    ]

    ALLOWED_UPLOAD_EXT = {
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv",
        ".png", ".jpg", ".jpeg", ".webp", ".zip",
    }
