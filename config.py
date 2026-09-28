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

    # Short AI summaries of uploaded PDFs. Any service with an OpenAI-style
    # chat API works: Google Gemini (free tier), Groq, xAI Grok, OpenAI …
    # AI_* names win; the older XAI_* names still work. No key = feature off.
    AI_API_KEY = (os.getenv("AI_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    AI_API_URL = (os.getenv("AI_API_URL") or os.getenv("XAI_API_URL")
                  or "https://api.x.ai/v1/chat/completions")
    AI_MODEL = os.getenv("AI_MODEL") or os.getenv("XAI_MODEL") or "grok-4"
    # for scanned PDFs, read as pictures; must be a model that takes images
    AI_VISION_MODEL = os.getenv("AI_VISION_MODEL") or os.getenv("XAI_VISION_MODEL") or AI_MODEL
    # shown under each summary: "by Gemini"
    AI_NAME = os.getenv("AI_NAME") or ("Grok" if "x.ai" in AI_API_URL else "AI")

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
