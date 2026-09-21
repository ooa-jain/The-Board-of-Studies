"""MongoDB access layer, indexes and first-run bootstrap."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone

import bcrypt
from pymongo import ASCENDING, MongoClient

from . import ugc_rules as U

_client: MongoClient | None = None
_db = None


# ---------------------------------------------------------------------------
# connection
# ---------------------------------------------------------------------------

def init_db(app):
    global _client, _db
    _client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=8000, tz_aware=True)
    _db = _client[app.config["MONGO_DB"]]
    _ensure_indexes()
    _bootstrap(app)
    return _db


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialised. Call init_db(app) first.")
    return _db


def now():
    return datetime.now(timezone.utc)


def _ensure_indexes():
    d = _db
    d.users.create_index([("username", ASCENDING)], unique=True)
    d.departments.create_index([("dept_code", ASCENDING)], unique=True)
    d.departments.create_index([("campus", ASCENDING)])
    d.departments.create_index([("school", ASCENDING)])
    d.submissions.create_index([("dept_code", ASCENDING), ("academic_year", ASCENDING)], unique=True)
    d.audit.create_index([("at", ASCENDING)])
    d.files.create_index([("dept_code", ASCENDING), ("stage", ASCENDING)])
    d.login_attempts.create_index([("username", ASCENDING), ("at", ASCENDING)])
    d.import_batches.create_index([("at", ASCENDING)])
    try:
        # Failed attempts and import previews are both scratch; let the server
        # sweep them up. Not every deployment (or mongomock) supports TTL
        # indexes, and neither collection depends on one.
        d.login_attempts.create_index([("at", ASCENDING)], expireAfterSeconds=24 * 3600)
        d.import_batches.create_index([("at", ASCENDING)], expireAfterSeconds=6 * 3600)
    except Exception:  # pragma: no cover - depends on the server
        pass


# ---------------------------------------------------------------------------
# passwords
# ---------------------------------------------------------------------------

_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
_PW_SYMBOLS = "@#$%&*"


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except (ValueError, AttributeError):
        return False


def generate_password(length: int = 12) -> str:
    """Readable but strong: no look-alike characters, one symbol, one digit."""
    body = "".join(secrets.choice(_PW_ALPHABET) for _ in range(length - 2))
    return body + secrets.choice(string.digits) + secrets.choice(_PW_SYMBOLS)


def slugify_username(dept_code: str, dept_name: str = "") -> str:
    """A login name derived from the department code — never from a person."""
    base = (dept_code or dept_name or "dept").strip().lower()
    base = "".join(ch if ch.isalnum() else "." for ch in base)
    while ".." in base:
        base = base.replace("..", ".")
    return base.strip(".")[:40]


def issue_department_login(db, dept, actor="system", reset=False):
    """Create or reset one department's login and return (username, password).

    Both halves come from the department itself: the username from its code,
    the password freshly generated. Single, bulk and import all call this, so
    a login issued one way is identical to one issued another.
    """
    dept_code = dept["dept_code"]
    username = dept.get("username") or slugify_username(dept_code, dept.get("dept_name", ""))

    # Only a *different* department holding this name forces a suffix.
    clash = db.users.find_one({"username": username})
    if clash and clash.get("dept_code") != dept_code:
        username = f"{username}.{dept_code.lower()}"

    password = generate_password()
    db.users.update_one(
        {"username": username},
        {"$set": {"username": username,
                  "password": hash_password(password),
                  "role": "department",
                  "name": dept.get("dept_name", dept_code),
                  "dept_code": dept_code,
                  "active": dept.get("active", True),
                  "must_change": False,
                  "updated_at": now()},
         "$setOnInsert": {"created_at": now()}},
        upsert=True)

    db.departments.update_one(
        {"_id": dept["_id"]},
        {"$set": {"username": username,
                  "initial_password": password,
                  "credentials_generated_at": now(),
                  "credentials_generated_by": actor},
         "$unset": {"first_login_at": ""}})

    return username, password


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------

def _bootstrap(app):
    d = _db
    if not d.users.find_one({"role": "admin"}):
        d.users.insert_one({
            "username": app.config["ADMIN_USERNAME"],
            "password": hash_password(app.config["ADMIN_PASSWORD"]),
            "role": "admin",
            "name": app.config["ADMIN_NAME"],
            "active": True,
            "must_change": True,
            "created_at": now(),
        })
        app.logger.info("Bootstrap admin created: %s", app.config["ADMIN_USERNAME"])

    if not d.rules.find_one({"_id": "ugc"}):
        d.rules.insert_one({
            "_id": "ugc",
            "table2": U.DEFAULT_TABLE_2,
            "totals": U.DEFAULT_TOTALS,
            "in_lieu": U.IN_LIEU_RULE,
            "other": U.DEFAULT_OTHER_RULES,
            "updated_at": now(),
            "updated_by": "system",
        })

    if not d.settings.find_one({"_id": "app"}):
        d.settings.insert_one({
            "_id": "app",
            "academic_year": app.config["ACADEMIC_YEAR"],
            "submissions_open": True,
            "banner": "",
            "updated_at": now(),
        })


# ---------------------------------------------------------------------------
# convenience accessors
# ---------------------------------------------------------------------------

def settings():
    return get_db().settings.find_one({"_id": "app"}) or {}


def rules_doc():
    return get_db().rules.find_one({"_id": "ugc"}) or {}


def audit(actor: str, action: str, target: str = "", detail=None):
    get_db().audit.insert_one({
        "actor": actor, "action": action, "target": target,
        "detail": detail or {}, "at": now(),
    })
