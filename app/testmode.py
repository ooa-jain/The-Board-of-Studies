"""
Test mode — a sandbox for training, demonstrations and release checks.

Switched on with ``TEST_MODE=1`` and off by default. While it is on:

* a standing ribbon appears on every page, so nobody mistakes the sandbox for
  the live portal;
* a demo department set can be seeded with one click, logins and all;
* any account can be signed into without its password, from the test console
  or the sign-in screen;
* every stage of a department's record can be opened at once, so stage 11 can
  be exercised without filling the ten before it;
* the whole cycle can be wiped and started again.

Every one of those routes refuses to exist when test mode is off — the
blueprint answers 404, not 403, so a probe cannot even tell it is there.
"""

from __future__ import annotations

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)

from .db import (audit, generate_password, get_db, hash_password,
                 issue_department_login, now, slugify_username)
from .schema import STAGE_KEYS
from .workflow import get_or_create_submission, unlock_stage

bp = Blueprint("test", __name__)

#: The demo department set. Two campuses, five schools, codes short enough to
#: type. The dev server and the test console seed the same list, so a demo and
#: a test run look at identical data.
DEMO_DEPARTMENTS = [
    ("School of Commerce and Management", "Department of Commerce", "COM", "Bengaluru"),
    ("School of Commerce and Management", "Department of Business Administration",
     "BBA", "Bengaluru"),
    ("Faculty of Engineering and Technology",
     "Department of Computer Science and Engineering", "CSE", "Bengaluru"),
    ("School of Sciences", "Department of Physics", "PHY", "Bengaluru"),
    ("School of Humanities and Social Sciences", "Department of English", "ENG", "Bengaluru"),
    ("School of Commerce and Management", "Department of Commerce", "COM-KC", "Kochi"),
    ("School of Sciences", "Department of Computer Science", "CSC-KC", "Kochi"),
]


def enabled() -> bool:
    return bool(current_app.config.get("TEST_MODE"))


@bp.before_request
def _only_in_test_mode():
    if not enabled():
        abort(404)


# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------

def seed_departments(actor="test-mode", with_logins=True):
    """Add any missing demo department, and a login for it. Idempotent."""
    db = get_db()
    made, logins = 0, []
    for school, name, code, campus in DEMO_DEPARTMENTS:
        existing = db.departments.find_one({"dept_code": code})
        if not existing:
            db.departments.insert_one({
                "dept_code": code, "dept_name": name, "school": school, "campus": campus,
                "hod_name": "Dr. " + name.split()[-1] + " Head",
                "hod_designation": "Head of the Department",
                "hod_email": f"{code.lower()}.hod@jainuniversity.ac.in",
                "hod_phone": "9900000000",
                "active": True, "created_at": now(), "updated_at": now(),
            })
            made += 1
        dept = db.departments.find_one({"dept_code": code})
        if with_logins and not dept.get("username"):
            username, password = issue_department_login(db, dept, actor=actor)
            logins.append((username, password, name))
    return made, logins


def demo_accounts():
    """Every account the console can sign in as, department logins first."""
    db = get_db()
    rows = []
    for d in db.departments.find({"username": {"$nin": [None, ""]}}).sort("dept_name", 1):
        rows.append({
            "username": d["username"],
            "name": d.get("dept_name", d["dept_code"]),
            "role": "department",
            "detail": f"{d.get('campus', '')} · {d['dept_code']}",
            "password": d.get("initial_password"),
            "active": d.get("active", True),
        })
    for u in db.users.find({"role": "admin"}).sort("username", 1):
        rows.insert(0, {
            "username": u["username"],
            "name": u.get("name", u["username"]),
            "role": "admin",
            "detail": "Office of Academics",
            "password": None,
            "active": u.get("active", True),
        })
    return rows


# ---------------------------------------------------------------------------
# the console
# ---------------------------------------------------------------------------

@bp.route("/")
def console():
    db = get_db()
    year = (db.settings.find_one({"_id": "app"}) or {}).get("academic_year") \
        or current_app.config["ACADEMIC_YEAR"]
    departments = list(db.departments.find({"active": True}).sort("dept_name", 1))
    return render_template(
        "test/console.html",
        accounts=demo_accounts(),
        departments=departments,
        year=year,
        counts={
            "departments": db.departments.count_documents({}),
            "logins": db.users.count_documents({"role": "department"}),
            "submissions": db.submissions.count_documents({}),
            "files": db.files.count_documents({}),
            "audit": db.audit.count_documents({}),
        },
        seeded=all(db.departments.find_one({"dept_code": c})
                   for _, _, c, _ in DEMO_DEPARTMENTS),
    )


@bp.post("/seed")
def seed():
    made, logins = seed_departments(actor=_actor())
    audit(_actor(), "testmode.seed", detail={"added": made, "logins": len(logins)})
    if made or logins:
        flash(f"Seeded {made} demo department(s) and issued {len(logins)} login(s).", "success")
    else:
        flash("The demo departments are already in place.", "info")
    return redirect(url_for("test.console"))


@bp.post("/signin")
def signin():
    """Sign in as any account without its password. Test mode only."""
    username = (request.form.get("username") or "").strip().lower()
    user = get_db().users.find_one({"username": username})
    if not user:
        flash(f"There is no account called “{username}”.", "error")
        return redirect(url_for("test.console"))
    if not user.get("active", True):
        flash(f"“{username}” is disabled. Re-enable the department first.", "error")
        return redirect(url_for("test.console"))

    session["user"] = {
        "username": user["username"],
        "role": user["role"],
        "name": user.get("name") or user["username"],
        "dept_code": user.get("dept_code"),
        "must_change": False,
        "via_test_mode": True,
    }
    session.permanent = True
    audit(user["username"], "testmode.signin", request.remote_addr or "")
    flash(f"Signed in as {session['user']['name']} through test mode.", "info")
    if user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("dept.dashboard"))


@bp.post("/open-all/<dept_code>")
def open_all(dept_code):
    """Open every stage for one department, ignoring the sequential lock."""
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code})
    if not dept:
        abort(404)
    year = (db.settings.find_one({"_id": "app"}) or {}).get("academic_year") \
        or current_app.config["ACADEMIC_YEAR"]
    get_or_create_submission(dept_code, year)
    for key in STAGE_KEYS:
        unlock_stage(dept_code, year, key, actor=_actor())
    audit(_actor(), "testmode.open_all", dept_code)
    flash(f"Every stage is open for {dept['dept_name']}. Sign in as that department "
          f"to fill any of them.", "success")
    return redirect(url_for("test.console"))


@bp.post("/reset")
def reset():
    """Wipe the cycle: submissions, uploads, departments and their logins.

    The administrator account, the credit rules and the portal settings stay —
    otherwise there would be no way back into the portal afterwards.
    """
    if (request.form.get("confirm") or "").strip().upper() != "RESET":
        flash("Type RESET in the box to confirm. Nothing has been deleted.", "error")
        return redirect(url_for("test.console"))

    db = get_db()
    removed = {
        "submissions": db.submissions.delete_many({}).deleted_count,
        "files": db.files.delete_many({}).deleted_count,
        "departments": db.departments.delete_many({}).deleted_count,
        "logins": db.users.delete_many({"role": "department"}).deleted_count,
        "import_batches": db.import_batches.delete_many({}).deleted_count,
    }
    audit(_actor(), "testmode.reset", detail=removed)

    if request.form.get("reseed") == "on":
        seed_departments(actor=_actor())
        flash("Test data cleared and the demo departments seeded again.", "success")
    else:
        flash("Test data cleared. The administrator account, the credit rules and the "
              "portal settings are untouched.", "success")
    return redirect(url_for("test.console"))


@bp.route("/status")
def status():
    """A machine-readable summary, for smoke tests and health checks."""
    db = get_db()
    return jsonify({
        "test_mode": True,
        "academic_year": (db.settings.find_one({"_id": "app"}) or {}).get("academic_year"),
        "departments": db.departments.count_documents({}),
        "submissions": db.submissions.count_documents({}),
        "signed_in_as": (session.get("user") or {}).get("username"),
    })


def _actor():
    return (session.get("user") or {}).get("username") or "test-mode"


# ---------------------------------------------------------------------------
# used by tools/devserver.py so a demo and a test run seed identically
# ---------------------------------------------------------------------------

def seed_for_devserver(db, admin_username=""):
    """Seed demo departments with logins, returning them for printing."""
    rows = []
    for school, name, code, campus in DEMO_DEPARTMENTS:
        if db.departments.find_one({"dept_code": code}):
            continue
        db.departments.insert_one({
            "dept_code": code, "dept_name": name, "school": school, "campus": campus,
            "hod_name": "Dr. " + name.split()[-1] + " Head",
            "hod_designation": "Head of the Department",
            "hod_email": f"{code.lower()}.hod@jainuniversity.ac.in",
            "hod_phone": "9900000000",
            "active": True, "created_at": now(), "updated_at": now(),
        })
        username = slugify_username(code, name)
        password = generate_password()
        db.users.insert_one({
            "username": username, "password": hash_password(password),
            "role": "department", "name": name, "dept_code": code,
            "active": True, "must_change": False, "created_at": now(),
        })
        db.departments.update_one({"dept_code": code},
                                  {"$set": {"username": username,
                                            "initial_password": password,
                                            "credentials_generated_at": now(),
                                            "credentials_generated_by": "devserver"}})
        rows.append((username, password, name))
    return rows
