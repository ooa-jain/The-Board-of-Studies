"""Settings › Team & access: the people in the Office who use the admin side.

A Full admin adds a person by their email (which is their username), gives
them a password — typed, or generated — and chooses what they may do: for
each section of the menu None, View or Edit, Delete on its own, and which
departments they see. Their password is shown once, on a slip to print or a
message to copy; at their first sign-in they set their own.

The routes sit on the admin blueprint, so the access check before every
admin page applies to them too: they are for Full admins only.
"""

from __future__ import annotations

import re

from flask import abort, flash, redirect, render_template, request, session, url_for

from .access import PRESETS, SECTIONS, SECTION_KEYS, summary
from .admin import _actor, _year, bp
from .auth import admin_required
from .db import audit, generate_password, get_db, hash_password, now

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _member(username):
    u = get_db().users.find_one({"username": username, "role": "admin", "team": True})
    return u or abort(404)


def _options():
    """The departments to choose from, and the schools and campuses they make."""
    db = get_db()
    depts = list(db.departments.find({}, {"dept_code": 1, "dept_name": 1, "school": 1, "campus": 1, "active": 1})
                 .sort([("campus", 1), ("school", 1), ("dept_name", 1)]))
    schools = sorted({d.get("school") for d in depts if d.get("school")})
    campuses = sorted({d.get("campus") for d in depts if d.get("campus")})
    return depts, schools, campuses


def _values(member=None, form=None):
    """What the form shows: what was just typed (after an error), else the
    person's access as it stands, else a Viewer for every department."""
    if form:
        return {"name": form.get("name", ""), "email": form.get("email", ""),
                "preset": form.get("preset") or "custom",
                "sections": {k: form.get("sec_" + k) or "none" for k in SECTION_KEYS},
                "delete": form.get("delete") == "on", "pw_mode": form.get("pw_mode") or "generate",
                "scope": form.get("scope") or "all", "codes": set(form.getlist("codes")),
                "schools": set(form.getlist("schools")), "campuses": set(form.getlist("campuses"))}
    if member:
        acc = member.get("access") or {}
        secs = {k: (acc.get("sections") or {}).get(k) or "none" for k in SECTION_KEYS}
        preset = "full" if member.get("full") else next(
            (k for k, p in PRESETS.items() if k != "full" and p["delete"] == bool(acc.get("delete"))
             and all(secs[x] == (p["sections"].get(x) or "none") for x in SECTION_KEYS)), "custom")
        sc = member.get("scope") or {}
        return {"name": member.get("name", ""), "email": member["username"], "preset": preset,
                "sections": secs, "delete": bool(acc.get("delete")), "pw_mode": "generate",
                "scope": "all" if sc.get("all", True) else "selected", "codes": set(sc.get("codes") or []),
                "schools": set(sc.get("schools") or []), "campuses": set(sc.get("campuses") or [])}
    viewer = PRESETS["viewer"]
    return {"name": "", "email": "", "preset": "viewer",
            "sections": {k: viewer["sections"].get(k) or "none" for k in SECTION_KEYS}, "delete": False,
            "pw_mode": "generate", "scope": "all", "codes": set(), "schools": set(), "campuses": set()}


def _form(member=None, form=None):
    depts, schools, campuses = _options()
    return render_template("admin/team_form.html", member=member, v=_values(member, form), depts=depts,
                           schools=schools, campuses=campuses, presets=PRESETS, sections=SECTIONS)


def _read_form(f, editing=None):
    """The form, as a user record's access, scope and name — or an error."""
    name = (f.get("name") or "").strip()[:80]
    email = (f.get("email") or "").strip().lower()
    if not editing:
        if not EMAIL.match(email):
            return None, "Give the person's email address — it is their username."
        if get_db().users.find_one({"username": email}):
            return None, f"{email} already has an account on the portal."
    if not name:
        return None, "Give the person's name, as it should show in the menu and the audit log."
    full = f.get("preset") == "full"
    sections = {k: (f.get("sec_" + k) if f.get("sec_" + k) in ("none", "view", "edit") else "none")
                for k in SECTION_KEYS}
    if not full and all(v == "none" for v in sections.values()):
        return None, "Give at least one section View or Edit — otherwise there is nothing they can open."
    every = f.get("scope") != "selected"
    scope = {"all": every,
             "codes": [] if every else sorted(set(f.getlist("codes"))),
             "schools": [] if every else sorted(set(f.getlist("schools"))),
             "campuses": [] if every else sorted(set(f.getlist("campuses")))}
    if not full and not every and not (scope["codes"] or scope["schools"] or scope["campuses"]):
        return None, "Choose the departments they may see — or choose “All departments”."
    rec = {"name": name, "full": full,
           "access": {"sections": sections, "delete": f.get("delete") == "on"},
           "scope": scope, "updated_at": now(), "updated_by": _actor()}
    if not editing:
        rec["username"] = email
        rec["email"] = email
    return rec, None


def _password_from(f):
    """The password typed in, or one made up: (password, error)."""
    if f.get("pw_mode") == "type":
        pw = f.get("password") or ""
        if len(pw) < 10:
            return None, "A typed password must be at least 10 characters long."
        return pw, None
    return generate_password(12), None


def _slip(member, password):
    """Shown once: what to hand the person."""
    session["team_slip"] = {"username": member["username"], "password": password}
    return redirect(url_for("admin.team_slip", username=member["username"]))


@bp.route("/team")
@admin_required
def team():
    from .db import settings
    db = get_db()
    me = session["user"]["username"]
    first = list(db.users.find({"role": "admin", "team": {"$ne": True}}))
    people = list(db.users.find({"role": "admin", "team": True}).sort([("active", -1), ("name", 1)]))
    for u in first + people:
        u["summary"] = summary(u)
        u["is_me"] = u["username"] == me
        u["off"] = not u.get("active", True)
    return render_template("admin/team.html", first=first, people=people, sections=SECTIONS,
                           share_links=settings().get("share_links") or "anyone")


@bp.route("/team/new", methods=["GET", "POST"])
@admin_required
def team_new():
    if request.method == "POST":
        rec, err = _read_form(request.form)
        pw, perr = _password_from(request.form)
        err = err or perr
        if err:
            flash(err, "error")
            return _form(None, request.form)
        rec.update(role="admin", team=True, active=True, must_change=True,
                   password=hash_password(pw), created_at=now(), created_by=_actor(),
                   credentials_generated_at=now())
        get_db().users.insert_one(rec)
        audit(_actor(), "team.added", rec["username"], {"access": summary(rec)})
        flash(f"{rec['name']} can now sign in. Hand over the username and password below — "
              "the password is shown only this once.", "success")
        return _slip(rec, pw)
    return _form()


@bp.route("/team/<username>/edit", methods=["GET", "POST"])
@admin_required
def team_edit(username):
    member = _member(username)
    if request.method == "POST":
        rec, err = _read_form(request.form, editing=member)
        if not err and member["username"] == session["user"]["username"] and not rec["full"]:
            err = "You cannot take Full admin away from yourself — ask another Full admin."
        if err:
            flash(err, "error")
            return _form(member, request.form)
        get_db().users.update_one({"_id": member["_id"]}, {"$set": rec})
        audit(_actor(), "team.access", member["username"], {"access": summary({**member, **rec})})
        flash(f"{rec['name']}'s access is saved. It applies from their next click.", "success")
        return redirect(url_for("admin.team"))
    return _form(member)


@bp.post("/team/<username>/password")
@admin_required
def team_password(username):
    member = _member(username)
    pw, err = _password_from(request.form)
    if err:
        flash(err, "error")
        return redirect(url_for("admin.team"))
    get_db().users.update_one({"_id": member["_id"]}, {"$set": {
        "password": hash_password(pw), "must_change": True, "credentials_generated_at": now(),
        "updated_by": _actor()}})
    audit(_actor(), "team.password", member["username"])
    flash(f"A new password for {member.get('name')}. They set their own when they next sign in.", "success")
    return _slip(member, pw)


@bp.route("/team/<username>/slip")
@admin_required
def team_slip(username):
    member = _member(username)
    held = session.pop("team_slip", None)
    if not held or held.get("username") != member["username"]:
        flash("The password is shown only once, when it is made. Give them a new one if it was not passed on.",
              "info")
        return redirect(url_for("admin.team"))
    return render_template("admin/team_slip.html", member=member, password=held["password"],
                           what=summary(member), login_url=url_for("public.landing", _external=True),
                           year=_year())


@bp.post("/team/<username>/toggle")
@admin_required
def team_toggle(username):
    member = _member(username)
    if member["username"] == session["user"]["username"]:
        flash("You cannot turn off your own access.", "error")
        return redirect(url_for("admin.team"))
    on = not member.get("active", True)
    get_db().users.update_one({"_id": member["_id"]}, {"$set": {"active": on}})
    audit(_actor(), "team.on" if on else "team.off", member["username"])
    flash(f"{member.get('name')} can sign in again." if on else
          f"{member.get('name')} can no longer sign in; anything open is closed at their next click.", "info")
    return redirect(url_for("admin.team"))


@bp.post("/team/<username>/delete")
@admin_required
def team_delete(username):
    member = _member(username)
    if member["username"] == session["user"]["username"]:
        flash("You cannot remove yourself.", "error")
        return redirect(url_for("admin.team"))
    get_db().users.delete_one({"_id": member["_id"]})
    audit(_actor(), "team.removed", member["username"])
    flash(f"{member.get('name')} is removed. What they did stays in the audit log.", "success")
    return redirect(url_for("admin.team"))


@bp.post("/team/links")
@admin_required
def team_links():
    """Who may open the links in the downloaded Excel and Word files."""
    mode = "team" if request.form.get("share_links") == "team" else "anyone"
    get_db().settings.update_one({"_id": "app"}, {"$set": {"share_links": mode}}, upsert=True)
    audit(_actor(), "settings.share_links", mode)
    flash("Links in downloads now open only for people signed in to the portal who may see that department."
          if mode == "team" else "Links in downloads open for anyone who has the link.", "success")
    return redirect(url_for("admin.team") + "#links")

