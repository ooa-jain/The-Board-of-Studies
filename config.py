"""Configuration for the JAIN OoA BoS Data Repository Portal."""
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

    # Test mode — a sandbox for training and for checking the flow end to end.
    # It seeds demo departments, allows one-click sign-in as any demo account
    # and lets the whole cycle be wiped and started again. It must never be on
    # for the live portal, so every page it touches carries a standing ribbon.
    TEST_MODE = _bool("TEST_MODE", False)

    # How long the landing page stays "seen" before a visitor is shown it
    # again. The marketing page is an introduction, not a doorway you walk
    # through every morning.
    LANDING_SEEN_DAYS = int(os.getenv("LANDING_SEEN_DAYS", "180"))

    # Off only for the test suite, where the client has no browser to hold a
    # token. Never turn this off for a deployment.
    CSRF_PROTECT = _bool("CSRF_PROTECT", True)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", not DEBUG)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 10  # 10 hours

    CAMPUSES = ["Bengaluru", "Kochi"]

    ALLOWED_UPLOAD_EXT = {
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv",
        ".png", ".jpg", ".jpeg", ".webp", ".zip",
    }
