"""Login, logout, password change, and the access decorators."""

from __future__ import annotations

from functools import wraps

from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from .db import audit, check_password, get_db, hash_password, now

bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# decorators
# ---------------------------------------------------------------------------

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        u = session.get("user")
        if not u:
            return redirect(url_for("auth.login", next=request.path))
        if u.get("role") != "admin":
            abort(403)
        return fn(*a, **kw)
    return wrapper


def department_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        u = session.get("user")
        if not u:
            return redirect(url_for("auth.login", next=request.path))
        if u.get("role") != "department":
            abort(403)
        return fn(*a, **kw)
    return wrapper


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

#: Wrong passwords allowed for one username before it is held, and for how
#: long. The passwords here are generated and handed out on paper, so an
#: unthrottled login form is the weak point.
MAX_FAILURES = 8
LOCKOUT_MINUTES = 15


def safe_next(target: str | None) -> str | None:
    r"""A ``?next=`` value that can only point back into this portal.

    ``//evil.example`` and ``/\evil.example`` both start with a slash and are
    both read by browsers as somewhere else entirely, so "starts with /" was
    never enough on its own.
    """
    if not target:
        return None
    target = target.strip()
    if not target.startswith("/"):
        return None
    if target.startswith("//") or target.startswith("/\\"):
        return None
    if "\\" in target or "\n" in target or "\r" in target:
        return None
    return target


def _recent_failures(db, username: str) -> int:
    since = now() - timedelta(minutes=LOCKOUT_MINUTES)
    return db.login_attempts.count_documents({"username": username, "at": {"$gte": since}})


def _record_failure(db, username: str, ip: str):
    db.login_attempts.insert_one({"username": username, "ip": ip, "at": now()})


def _clear_failures(db, username: str):
    db.login_attempts.delete_many({"username": username})


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return _home_for(session["user"])

    db = get_db()
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        ip = request.remote_addr or ""

        if username and _recent_failures(db, username) >= MAX_FAILURES:
            audit(username, "login.throttled", ip)
            error = (f"Too many failed attempts for that username. Wait {LOCKOUT_MINUTES} "
                     f"minutes, or ask the Office of Academics to reset the password.")
            return render_template("login.html", error=error,
                                   accounts=_test_accounts()), 429

        user = db.users.find_one({"username": username, "active": True})

        if not user or not check_password(password, user["password"]):
            error = "That username and password do not match any account."
            if username:
                _record_failure(db, username, ip)
            audit(username or "unknown", "login.failed", ip)
        else:
            payload = {
                "username": user["username"],
                "role": user["role"],
                "name": user.get("name") or user["username"],
                "dept_code": user.get("dept_code"),
                "must_change": bool(user.get("must_change")),
            }
            # A fresh session id on sign-in, so a token handed out before
            # anybody authenticated cannot be carried across the boundary.
            session.clear()
            session["user"] = payload
            session.permanent = True
            _clear_failures(db, username)
            db.users.update_one({"_id": user["_id"]},
                                {"$set": {"last_login": now()},
                                 "$inc": {"login_count": 1}})
            if user["role"] == "department" and user.get("dept_code"):
                # once the department has signed in, the admin no longer sees
                # the generated password in the clear
                db.departments.update_one(
                    {"dept_code": user["dept_code"], "first_login_at": {"$exists": False}},
                    {"$set": {"first_login_at": now()}, "$unset": {"initial_password": ""}})
            audit(user["username"], "login.ok", ip)
            if payload["must_change"]:
                flash("Change the password you were issued before you go any further.", "info")
                return redirect(url_for("auth.change_password"))
            nxt = safe_next(request.args.get("next"))
            if nxt:
                return redirect(nxt)
            return _home_for(payload)

    return render_template("login.html", error=error, accounts=_test_accounts()), \
        (401 if error else 200)


def _test_accounts():
    """The one-click sign-in list, and only while test mode is on."""
    if not current_app.config.get("TEST_MODE"):
        return []
    from .testmode import demo_accounts
    return demo_accounts()


def _home_for(user):
    if user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("dept.dashboard"))


@bp.route("/logout")
def logout():
    u = session.get("user")
    if u:
        audit(u["username"], "logout")
    # The whole session goes, not just the user key — anything else held in it
    # belonged to that sign-in too.
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        current = request.form.get("current") or ""
        new = request.form.get("new") or ""
        confirm = request.form.get("confirm") or ""
        db = get_db()
        user = db.users.find_one({"username": session["user"]["username"]})

        if not check_password(current, user["password"]):
            error = "Your current password is not correct."
        elif len(new) < 10:
            error = "The new password must be at least 10 characters long."
        elif new != confirm:
            error = "The two new passwords do not match."
        elif new == current:
            error = "The new password must be different from the current one."
        else:
            db.users.update_one({"_id": user["_id"]},
                                {"$set": {"password": hash_password(new),
                                          "must_change": False,
                                          "password_changed_at": now()}})
            session["user"]["must_change"] = False
            session.modified = True
            audit(user["username"], "password.changed")
            flash("Your password has been changed.", "success")
            return _home_for(session["user"])

    return render_template("change_password.html", error=error)
