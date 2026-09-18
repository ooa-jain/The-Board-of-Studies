"""Login, logout, password change, and the access decorators."""

from __future__ import annotations

from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

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
# routes
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return _home_for(session["user"])

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        db = get_db()
        user = db.users.find_one({"username": username, "active": True})

        if not user or not check_password(password, user["password"]):
            error = "That username and password do not match any account."
            audit(username or "unknown", "login.failed", request.remote_addr or "")
        else:
            payload = {
                "username": user["username"],
                "role": user["role"],
                "name": user.get("name") or user["username"],
                "dept_code": user.get("dept_code"),
                "must_change": bool(user.get("must_change")),
            }
            session["user"] = payload
            session.permanent = True
            db.users.update_one({"_id": user["_id"]},
                                {"$set": {"last_login": now()},
                                 "$inc": {"login_count": 1}})
            if user["role"] == "department" and user.get("dept_code"):
                # once the department has signed in, the admin no longer sees
                # the generated password in the clear
                db.departments.update_one(
                    {"dept_code": user["dept_code"], "first_login_at": {"$exists": False}},
                    {"$set": {"first_login_at": now()}, "$unset": {"initial_password": ""}})
            audit(user["username"], "login.ok", request.remote_addr or "")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return _home_for(payload)

    return render_template("login.html", error=error)


def _home_for(user):
    if user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("dept.dashboard"))


@bp.route("/logout")
def logout():
    u = session.pop("user", None)
    if u:
        audit(u["username"], "logout")
    flash("You have been signed out.", "info")
    return redirect(url_for("public.landing"))


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
