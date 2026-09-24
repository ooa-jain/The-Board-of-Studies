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


_GRAMMAR = {"of", "and", "the", "for", "in"}


def _initials(text: str, keep: int = 4, drop=frozenset()) -> str:
    """Initials of a name, ignoring the grammar between the words.

    A single-word name has no initials worth the name, so the first few
    letters stand in: "Commerce" gives "comm", not "c".
    """
    words = [w for w in "".join(ch if ch.isalpha() else " " for ch in text).split()
             if w.lower() not in _GRAMMAR and w.lower() not in drop]
    if not words:
        return "dept"
    if len(words) == 1:
        return words[0][:keep].lower()
    return "".join(w[0] for w in words)[:keep].lower()


def department_username(db, dept) -> str:
    """department + school + a number, e.g. ``cse.scse.4713``.

    The department and the school say whose login it is at a glance; the
    number keeps the same department at a second campus from colliding with
    the first. Nothing about a person appears in it. The number is drawn
    again if it is already taken.
    """
    # "Department" is dropped from the first half because every department
    # carries it; "School" is kept in the second, where it tells the two
    # halves apart — cse.scse, not cse.cse.
    stem = (f"{_initials(dept.get('dept_name', ''), drop={'department'})}"
            f".{_initials(dept.get('school', ''))}")
    for _ in range(40):
        candidate = f"{stem}.{secrets.randbelow(9000) + 1000}"
        clash = db.users.find_one({"username": candidate})
        if not clash or clash.get("dept_code") == dept.get("dept_code"):
            return candidate
    # 40 collisions on a 4-digit number means something is very wrong; fall
    # back to the code, which is unique by construction.
    return slugify_username(dept["dept_code"])


def issue_department_login(db, dept, actor="system", reset=False):
    """Create or reset one department's login and return (username, password).

    Both halves are generated: the username from the department and its
    school plus a number, the password freshly drawn. Single, bulk, seed and
    import all call this, so a login issued one way is identical to one
    issued another, and nobody has to key one in by hand.

    A department that already has a username keeps it — reissuing is about
    the password, and changing someone's username along with it would lock
    them out of a name they have already been told.
    """
    dept_code = dept["dept_code"]
    username = dept.get("username") or department_username(db, dept)

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
