"""The portal's own words in Indian languages, for the department's pages.

The choice is kept per browser (a cookie), so each person on a shared
department login reads the portal in their own language. Only the portal's
wording changes: what the department types, programme and course names,
and the documents the portal makes stay as they are, in English.

The words live in app/translations/<code>.json, a map from the English text
on the page to its translation; static/js/i18n.js puts them on the page."""
import json
from functools import lru_cache
from pathlib import Path

from flask import request

LANGS = (("en", "English"), ("hi", "हिन्दी"), ("kn", "ಕನ್ನಡ"), ("ta", "தமிழ்"), ("ml", "മലയാളം"))
CODES = {c for c, _ in LANGS}
COOKIE = "bos_lang"
# a script's own font, for the letters Roboto has not got
FONTS = {"hi": "Noto+Sans+Devanagari", "kn": "Noto+Sans+Kannada", "ta": "Noto+Sans+Tamil",
         "ml": "Noto+Sans+Malayalam"}
FOLDER = Path(__file__).parent / "translations"


def current_lang(user=None):
    """The language this browser chose; English when none, and always
    English for the Office, whose pages are not translated."""
    if (user or {}).get("role") == "admin" and not (user or {}).get("acting"):
        return "en"
    code = request.cookies.get(COOKIE, "en") if request else "en"
    return code if code in CODES else "en"


@lru_cache(maxsize=8)
def _load(code, stamp):
    f = FOLDER / f"{code}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def words(code):
    """The translation map for a language (cached until the file changes)."""
    f = FOLDER / f"{code}.json"
    return _load(code, int(f.stat().st_mtime) if f.is_file() else 0)


def version(code):
    f = FOLDER / f"{code}.json"
    return int(f.stat().st_mtime) if f.is_file() else 0
