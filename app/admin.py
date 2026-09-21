"""Office of Academics administration console."""

from __future__ import annotations

import re
import uuid

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, session, url_for)

from . import ugc_rules as U
from .auth import admin_required
from .db import audit, get_db, issue_department_login, now, rules_doc
from .exporter import department_excel, institution_excel, submission_word
from .importer import parse_workbook
from .schema import STAGE_BY_KEY, STAGES
from .workflow import (compute_status, progress, relock_stage, return_stage,
                       stage_board, unlock_stage)

bp = Blueprint("admin", __name__)

#: A department code is the login name, so it has to survive being one.
DEPT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/.]{1,19}$")

#: "2027-28" or "2027-2028" — anything else and every submission filed this
#: year is orphaned under a year nobody can search for.
YEAR_RE = re.compile(r"^\d{4}-\d{2}(\d{2})?$")


def _year():
    from .db import settings
    return settings().get("academic_year") or current_app.config["ACADEMIC_YEAR"]


def _actor():
    return session["user"]["username"]


def _int(name: str, default=None, minimum=None, maximum=None):
    """A form number, or the default — never a 500 because somebody typed “ten”."""
    raw = (request.form.get(name) or "").strip()
    if not raw.lstrip("-").isdigit():
        return default
    value = int(raw)
    if minimum is not None and value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    year = _year()
    departments = list(db.departments.find({"active": True}).sort("dept_name", 1))
    subs = {s["dept_code"]: s for s in db.submissions.find({"academic_year": year})}

    rows, counts = [], {"not_started": 0, "in_progress": 0, "complete": 0}
    for d in departments:
        sub = subs.get(d["dept_code"])
        p = progress(sub) if sub else {"done": 0, "total": len(STAGES), "percent": 0}
        if not sub:
            state = "not_started"
        elif p["done"] == p["total"]:
            state = "complete"
        else:
            state = "in_progress"
        counts[state] += 1
        rows.append({"dept": d, "progress": p, "state": state,
                     "updated_at": (sub or {}).get("updated_at")})

    by_campus = {}
    for d in departments:
        c = d.get("campus", "—")
        by_campus.setdefault(c, {"total": 0, "complete": 0})
        by_campus[c]["total"] += 1
    for r in rows:
        if r["state"] == "complete":
            by_campus[r["dept"].get("campus", "—")]["complete"] += 1

    stage_counts = []
    for s in STAGES:
        done = sum(1 for sub in subs.values() if compute_status(sub, s["key"]) == "submitted")
        stage_counts.append({"title": s["title"], "key": s["key"], "done": done,
                             "total": len(departments)})

    # What actually needs doing, rather than another number to read: stages
    # sent back and still not resubmitted, and departments with no login.
    returned = []
    for d in departments:
        sub = subs.get(d["dept_code"])
        if not sub:
            continue
        for key, state in (sub.get("stages") or {}).items():
            if state.get("status") == "returned" and key in STAGE_BY_KEY:
                returned.append({"dept": d, "stage": STAGE_BY_KEY[key]["title"],
                                 "note": state.get("returned_note"),
                                 "at": state.get("returned_at")})
    returned.sort(key=lambda r: r["at"] or now(), reverse=True)

    no_login = [d for d in departments if not d.get("username")]

    return render_template("admin/dashboard.html", rows=rows, counts=counts,
                           by_campus=by_campus, stage_counts=stage_counts,
                           year=year, total=len(departments),
                           returned=returned[:8], returned_total=len(returned),
                           no_login=no_login,
                           unused_passwords=db.departments.count_documents(
                               {"initial_password": {"$exists": True}}),
                           recent=list(db.audit.find().sort("at", -1).limit(12)))


# ---------------------------------------------------------------------------
# department master
# ---------------------------------------------------------------------------

@bp.route("/departments")
@admin_required
def departments():
    db = get_db()
    q = {}
    campus = request.args.get("campus")
    school = request.args.get("school")
    search = (request.args.get("q") or "").strip()
    if campus:
        q["campus"] = campus
    if school:
        q["school"] = school
    if search:
        q["$or"] = [{"dept_name": {"$regex": search, "$options": "i"}},
                    {"dept_code": {"$regex": search, "$options": "i"}},
                    {"school": {"$regex": search, "$options": "i"}}]
    depts = list(db.departments.find(q).sort([("campus", 1), ("school", 1), ("dept_name", 1)]))
    return render_template("admin/departments.html", departments=depts,
                           schools=sorted(x for x in db.departments.distinct("school") if x),
                           campuses=current_app.config["CAMPUSES"],
                           filters={"campus": campus, "school": school, "q": search})


@bp.route("/departments/new", methods=["GET", "POST"])
@bp.route("/departments/<dept_code>/edit", methods=["GET", "POST"])
@admin_required
def department_form(dept_code=None):
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code}) if dept_code else None
    if dept_code and not dept:
        abort(404)

    if request.method == "POST":
        f = request.form
        code = (f.get("dept_code") or "").strip().upper()
        name = (f.get("dept_name") or "").strip()
        school = (f.get("school") or "").strip()
        campus = f.get("campus") or current_app.config["CAMPUSES"][0]
        active = f.get("active") == "on"

        # What was typed, so a rejected form comes back filled in rather than
        # blank. `active` has to be carried explicitly: an unticked checkbox
        # sends nothing, and the template cannot tell that from "new record".
        typed = {"dept_code": code, "dept_name": name, "school": school,
                 "campus": campus, "active": active}

        def reject(message):
            flash(message, "error")
            return render_template("admin/department_form.html", dept=typed,
                                   editing=bool(dept),
                                   campuses=current_app.config["CAMPUSES"]), 400

        if not code:
            return reject("Department code is required.")
        if not DEPT_CODE_RE.match(code):
            return reject(f"“{code}” cannot be a department code. Use 2–20 letters, numbers, "
                          f"hyphen, dot or slash, starting with a letter or a number.")
        if not name:
            return reject("Department name is required.")
        if not school:
            return reject("School or faculty is required.")
        if campus not in current_app.config["CAMPUSES"]:
            return reject(f"“{campus}” is not one of the campuses.")

        clash = db.departments.find_one({"dept_code": code})
        if clash and (not dept or clash["_id"] != dept["_id"]):
            return reject(f"Department code “{code}” is already in use by "
                          f"{clash.get('dept_name') or 'another department'}.")

        payload = {"dept_code": code, "dept_name": name, "school": school,
                   "campus": campus, "active": active, "updated_at": now()}

        if dept:
            db.departments.update_one({"_id": dept["_id"]}, {"$set": payload})
            # The login carries the department's name and its active flag, so
            # a rename or a disable has to reach the user record too.
            db.users.update_many({"dept_code": dept["dept_code"]},
                                 {"$set": {"name": name, "active": active,
                                           "dept_code": code}})
            if code != dept["dept_code"]:
                db.submissions.update_many({"dept_code": dept["dept_code"]},
                                           {"$set": {"dept_code": code}})
                db.files.update_many({"dept_code": dept["dept_code"]},
                                     {"$set": {"dept_code": code}})
            audit(_actor(), "department.updated", code)
            flash(f"{name} has been updated.", "success")
        else:
            payload["created_at"] = now()
            db.departments.insert_one(payload)
            audit(_actor(), "department.created", code)
            flash(f"{name} has been added. Generate its login from the department list.",
                  "success")
        return redirect(url_for("admin.departments"))

    return render_template("admin/department_form.html", dept=dept, editing=bool(dept),
                           campuses=current_app.config["CAMPUSES"])


@bp.route("/departments/<dept_code>/toggle", methods=["POST"])
@admin_required
def department_toggle(dept_code):
    db = get_db()
    d = db.departments.find_one({"dept_code": dept_code})
    if not d:
        abort(404)
    new = not d.get("active", True)
    db.departments.update_one({"_id": d["_id"]}, {"$set": {"active": new, "updated_at": now()}})
    # A department can hold more than one login over its life; every one of
    # them follows the department in or out.
    db.users.update_many({"dept_code": dept_code}, {"$set": {"active": new}})
    audit(_actor(), "department.active" if new else "department.disabled", dept_code)
    flash(f"{d['dept_name']} is now {'active' if new else 'disabled'}.", "info")
    return redirect(request.referrer or url_for("admin.departments"))


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------

@bp.route("/departments/<dept_code>/credentials", methods=["POST"])
@admin_required
def generate_credentials(dept_code):
    """Create or reset the department login. Username is derived from the code."""
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code}) or abort(404)

    had_login = bool(dept.get("username"))
    username, password = issue_department_login(db, dept, actor=_actor())

    audit(_actor(), "credentials.reset" if had_login else "credentials.generated", dept_code)

    if request.headers.get("Accept", "").startswith("application/json"):
        return jsonify({"ok": True, "username": username, "password": password})
    flash(f"Login generated for {dept['dept_name']}.", "success")
    return redirect(url_for("admin.credential_slip", dept_code=dept_code))


@bp.route("/departments/<dept_code>/slip")
@admin_required
def credential_slip(dept_code):
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code}) or abort(404)
    if not dept.get("initial_password"):
        flash("This department has already signed in, so the password is no longer visible. "
              "Reset it if they need a new one.", "info")
        return redirect(url_for("admin.departments"))
    return render_template("admin/credential_slip.html", dept=dept,
                           login_url=url_for("auth.login", _external=True), year=_year())


@bp.route("/credentials/bulk", methods=["POST"])
@admin_required
def bulk_credentials():
    """Generate logins for every active department that has none."""
    db = get_db()
    # A username left behind as null or "" by an older record is still a
    # department without a login; `$exists` alone walked straight past those.
    missing = list(db.departments.find(
        {"active": True, "$or": [{"username": {"$exists": False}},
                                 {"username": None}, {"username": ""}]}))
    made = 0
    for dept in missing:
        issue_department_login(db, dept, actor=_actor())
        made += 1

    audit(_actor(), "credentials.bulk", detail={"count": made})
    if made:
        flash(f"Generated logins for {made} department(s). "
              f"Print the credential sheet to hand them out.", "success")
    else:
        flash("Every active department already has a login.", "info")
    return redirect(url_for("admin.departments"))


@bp.route("/credentials/sheet")
@admin_required
def credential_sheet():
    """Printable sheet of every credential still in the clear."""
    db = get_db()
    depts = list(db.departments.find({"initial_password": {"$exists": True}})
                 .sort([("campus", 1), ("dept_name", 1)]))
    return render_template("admin/credential_sheet.html", departments=depts,
                           login_url=url_for("auth.login", _external=True), year=_year())


# ---------------------------------------------------------------------------
# Excel import
# ---------------------------------------------------------------------------

@bp.route("/import", methods=["GET", "POST"])
@admin_required
def import_departments():
    if request.method == "GET":
        return render_template("admin/import.html", preview=None, meta=None)

    upload = request.files.get("workbook")
    if not upload or not upload.filename:
        flash("Choose a workbook to upload.", "error")
        return redirect(url_for("admin.import_departments"))

    data = upload.read()
    sheet = request.form.get("sheet") or None
    default_campus = request.form.get("default_campus") or "Bengaluru"
    try:
        rows, meta = parse_workbook(data, sheet, default_campus=default_campus)
    except Exception as exc:
        flash(f"That file could not be read: {exc}", "error")
        return redirect(url_for("admin.import_departments"))

    db = get_db()
    existing = {d["dept_code"] for d in db.departments.find({}, {"dept_code": 1})}
    for r in rows:
        r["exists"] = r["dept_code"] in existing

    if not rows:
        flash("No department rows were found in that sheet. Check the sheet name and that "
              "the headings include a department column.", "error")
        return redirect(url_for("admin.import_departments"))

    # The preview is held in the database, not in the session cookie. A real
    # contact workbook runs to hundreds of rows; a cookie caps out at 4 KB, so
    # the old version silently dropped the batch and every import came back
    # "the preview expired".
    token = uuid.uuid4().hex
    db.import_batches.insert_one({"_id": token, "rows": rows, "meta": meta,
                                  "actor": _actor(), "at": now()})
    _prune_import_batches(db)
    session["import_batch"] = token

    return render_template("admin/import.html", preview=rows, meta=meta,
                           default_campus=default_campus,
                           campuses=current_app.config["CAMPUSES"])


def _prune_import_batches(db, keep=20):
    """Preview batches are scratch paper; keep the last few and drop the rest."""
    stale = list(db.import_batches.find({}, {"_id": 1}).sort("at", -1).skip(keep))
    if stale:
        db.import_batches.delete_many({"_id": {"$in": [b["_id"] for b in stale]}})


@bp.route("/import/commit", methods=["POST"])
@admin_required
def import_commit():
    db = get_db()
    token = session.pop("import_batch", None)
    batch = db.import_batches.find_one({"_id": token}) if token else None
    if not batch:
        flash("The import preview is no longer available. Upload the workbook again.", "error")
        return redirect(url_for("admin.import_departments"))
    rows = batch.get("rows") or []

    chosen = set(request.form.getlist("include"))
    overwrite = request.form.get("overwrite") == "on"
    make_logins = request.form.get("make_logins") == "on"

    added = updated = skipped = logins = 0
    for r in rows:
        if r["dept_code"] not in chosen:
            continue
        existing = db.departments.find_one({"dept_code": r["dept_code"]})
        payload = {k: r[k] for k in
                   ("dept_name", "school", "dept_code", "campus")}
        payload["updated_at"] = now()
        if existing and not overwrite:
            skipped += 1
        elif existing:
            db.departments.update_one({"_id": existing["_id"]}, {"$set": payload})
            updated += 1
        else:
            payload["active"] = True
            payload["created_at"] = now()
            db.departments.insert_one(payload)
            added += 1

        # A department that was skipped as already present may still be one
        # that never got a login. Issuing it is independent of the overwrite.
        if make_logins:
            dept = db.departments.find_one({"dept_code": r["dept_code"]})
            if dept and not dept.get("username"):
                issue_department_login(db, dept, actor=_actor())
                logins += 1

    db.import_batches.delete_one({"_id": token})

    audit(_actor(), "departments.imported",
          detail={"added": added, "updated": updated, "skipped": skipped, "logins": logins})
    flash(f"Import finished — {added} added, {updated} updated, {skipped} skipped, "
          f"{logins} login(s) generated.", "success")
    return redirect(url_for("admin.departments"))


# ---------------------------------------------------------------------------
# submission monitor
# ---------------------------------------------------------------------------

@bp.route("/submissions")
@admin_required
def submissions():
    db = get_db()
    year = _year()
    campus = request.args.get("campus")
    state = request.args.get("state")
    search = (request.args.get("q") or "").strip()

    q = {"active": True}
    if campus:
        q["campus"] = campus
    if search:
        q["$or"] = [{"dept_name": {"$regex": re.escape(search), "$options": "i"}},
                    {"dept_code": {"$regex": re.escape(search), "$options": "i"}},
                    {"school": {"$regex": re.escape(search), "$options": "i"}}]

    depts = list(db.departments.find(q).sort([("campus", 1), ("dept_name", 1)]))
    subs = {x["dept_code"]: x for x in db.submissions.find({"academic_year": year})}

    # Every active department gets a row, whether or not it has started. The
    # monitor is there to show who has *not* filed, and a department with no
    # submission document was exactly the one missing from it.
    rows = []
    for d in depts:
        sub = subs.get(d["dept_code"]) or {"dept_code": d["dept_code"],
                                           "academic_year": year, "stages": {}}
        p = progress(sub)
        row_state = ("complete" if p["done"] == p["total"]
                     else "not_started" if p["done"] == 0 and not sub.get("stages")
                     else "in_progress")
        if state and state != row_state:
            continue
        rows.append({"dept": d, "submission": sub, "progress": p,
                     "board": stage_board(sub), "state": row_state,
                     "started": bool(sub.get("stages")),
                     "updated_at": sub.get("updated_at")})

    rows.sort(key=lambda r: (-r["progress"]["percent"], r["dept"]["dept_name"]))
    return render_template("admin/submissions.html", rows=rows, year=year, stages=STAGES,
                           campuses=current_app.config["CAMPUSES"],
                           filters={"campus": campus, "state": state, "q": search},
                           returned_total=sum(
                               1 for r in rows
                               for b in r["board"] if b["status"] == "returned"))


@bp.route("/submissions/<dept_code>")
@admin_required
def submission_detail(dept_code):
    db = get_db()
    year = _year()
    dept = db.departments.find_one({"dept_code": dept_code})
    if not dept:
        abort(404)
    # Reading a record should not create one. Opening the monitor used to file
    # an empty submission for every department an administrator looked at.
    sub = db.submissions.find_one({"dept_code": dept_code, "academic_year": year}) or {
        "dept_code": dept_code, "academic_year": year, "stages": {}, "programmes": {},
        "status": "draft"}
    return render_template("admin/submission_detail.html", dept=dept, submission=sub,
                           board=stage_board(sub), progress=progress(sub),
                           year=year, STAGE_BY_KEY=STAGE_BY_KEY)


def _known_stage(stage_key):
    if stage_key not in STAGE_BY_KEY:
        abort(404)
    return STAGE_BY_KEY[stage_key]


@bp.route("/submissions/<dept_code>/<stage_key>/return", methods=["POST"])
@admin_required
def submission_return(dept_code, stage_key):
    stage = _known_stage(stage_key)
    note = (request.form.get("note") or "").strip()
    if len(note) < 5:
        flash("Say what needs correcting before you send a stage back.", "error")
        return redirect(url_for("admin.submission_detail", dept_code=dept_code))
    return_stage(dept_code, _year(), stage_key, note, _actor())
    audit(_actor(), "stage.returned", f"{dept_code}/{stage_key}", {"note": note})
    flash(f"“{stage['title']}” has been sent back for correction.", "info")
    return redirect(url_for("admin.submission_detail", dept_code=dept_code))


@bp.route("/submissions/<dept_code>/<stage_key>/unlock", methods=["POST"])
@admin_required
def submission_unlock(dept_code, stage_key):
    stage = _known_stage(stage_key)
    unlock_stage(dept_code, _year(), stage_key, _actor())
    audit(_actor(), "stage.unlocked", f"{dept_code}/{stage_key}")
    flash(f"“{stage['title']}” has been opened for this department, "
          f"ahead of the stages before it.", "info")
    return redirect(url_for("admin.submission_detail", dept_code=dept_code))


@bp.route("/submissions/<dept_code>/<stage_key>/relock", methods=["POST"])
@admin_required
def submission_relock(dept_code, stage_key):
    """Undo an override. Work already saved in the stage is left alone."""
    stage = _known_stage(stage_key)
    relock_stage(dept_code, _year(), stage_key, _actor())
    audit(_actor(), "stage.relocked", f"{dept_code}/{stage_key}")
    flash(f"“{stage['title']}” is back under the normal stage order.", "info")
    return redirect(url_for("admin.submission_detail", dept_code=dept_code))


# ---------------------------------------------------------------------------
# rule configuration
# ---------------------------------------------------------------------------

@bp.route("/rules", methods=["GET", "POST"])
@admin_required
def rules():
    db = get_db()
    doc = rules_doc()

    if request.method == "POST":
        table, problems = [], []
        for row in doc.get("table2", U.DEFAULT_TABLE_2):
            key = row["key"]
            new = {"sl": row["sl"], "key": key, "label": row["label"]}
            for track in ("ug3", "ug4"):
                lo = _int(f"{key}.{track}.min", default=0, minimum=0, maximum=400)
                hi = _int(f"{key}.{track}.max", default=None, minimum=0, maximum=400)
                if hi is not None and hi < lo:
                    problems.append(f"{row['label']} ({U.TRACKS.get(track, track)}): the maximum "
                                    f"is below the minimum.")
                    hi = None
                new[track] = {
                    "min": lo,
                    "max": hi,
                    "applicable": request.form.get(f"{key}.{track}.applicable") == "on",
                }
            table.append(new)

        # A non-numeric total used to be a 500. Keep the published value and
        # say which box was wrong instead.
        totals = {}
        for track in ("ug3", "ug4"):
            current = (doc.get("totals") or U.DEFAULT_TOTALS).get(track, U.DEFAULT_TOTALS[track])
            value = _int(f"total.{track}", default=None, minimum=1, maximum=1000)
            if value is None:
                problems.append(f"The {U.TRACKS.get(track, track)} total must be a whole number "
                                f"between 1 and 1000 — it has been left at {current}.")
                value = current
            totals[track] = value

        other = dict(doc.get("other") or U.DEFAULT_OTHER_RULES)
        limits = {"marks_per_credit": (1, 200), "max_credits_per_course": (1, 60),
                  "meeting_notice_days": (0, 120), "revision_benchmark_threshold": (0, 100)}
        for k, (lo, hi) in limits.items():
            raw = (request.form.get(f"other.{k}") or "").strip()
            value = _int(f"other.{k}", default=None, minimum=lo, maximum=hi)
            if value is None:
                if raw:
                    problems.append(f"“{k.replace('_', ' ')}” must be a whole number between "
                                    f"{lo} and {hi} — it has been left at {other.get(k)}.")
                continue
            other[k] = value

        db.rules.update_one({"_id": "ugc"},
                            {"$set": {"table2": table, "totals": totals, "other": other,
                                      "updated_at": now(), "updated_by": _actor()}},
                            upsert=True)
        audit(_actor(), "rules.updated", detail={"rejected": problems})
        if problems:
            flash("Saved, but some values were not accepted: " + " ".join(problems), "warning")
        else:
            flash("The credit rules have been updated. They apply to every validation "
                  "from now on.", "success")
        return redirect(url_for("admin.rules"))

    return render_template("admin/rules.html", doc=doc, tracks=U.TRACKS,
                           defaults=U.DEFAULT_TABLE_2, in_lieu=U.IN_LIEU_RULE)


@bp.route("/rules/reset", methods=["POST"])
@admin_required
def rules_reset():
    get_db().rules.update_one({"_id": "ugc"},
                              {"$set": {"table2": U.DEFAULT_TABLE_2,
                                        "totals": U.DEFAULT_TOTALS,
                                        "in_lieu": U.IN_LIEU_RULE,
                                        "other": U.DEFAULT_OTHER_RULES,
                                        "updated_at": now(), "updated_by": _actor()}},
                              upsert=True)
    audit(_actor(), "rules.reset")
    flash("Credit rules restored to the published UGC Table 2 values.", "success")
    return redirect(url_for("admin.rules"))


# ---------------------------------------------------------------------------
# settings, audit, exports
# ---------------------------------------------------------------------------

@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def app_settings():
    db = get_db()
    from .db import settings as read_settings

    if request.method == "POST":
        current = read_settings()
        year = (request.form.get("academic_year") or "").strip()
        banner = (request.form.get("banner") or "").strip()[:280]

        # An empty or malformed year orphans every record filed under it, and
        # the field was saved without a glance at what was in it.
        if not YEAR_RE.match(year):
            flash("The academic year must read like 2027-28 or 2027-2028. "
                  "Nothing has been changed.", "error")
            return render_template("admin/settings.html", settings=current,
                                   year_error=True), 400

        changed_year = year != (current.get("academic_year") or "")
        db.settings.update_one(
            {"_id": "app"},
            {"$set": {"academic_year": year,
                      "submissions_open": request.form.get("submissions_open") == "on",
                      "banner": banner,
                      "updated_at": now(),
                      "updated_by": _actor()}},
            upsert=True)
        audit(_actor(), "settings.updated", detail={"academic_year": year})
        if changed_year:
            filed = db.submissions.count_documents({"academic_year": year})
            flash(f"Settings saved. The active year is now {year} — "
                  f"{filed} record(s) are filed under it. Earlier years are untouched.",
                  "success")
        else:
            flash("Settings saved.", "success")
        return redirect(url_for("admin.app_settings"))

    return render_template("admin/settings.html", settings=read_settings())


PAGE_SIZE = 100


@bp.route("/audit")
@admin_required
def audit_log():
    db = get_db()
    actor = (request.args.get("actor") or "").strip()
    action = (request.args.get("action") or "").strip()
    page = max(1, request.args.get("page", type=int) or 1)

    q = {}
    if actor:
        q["actor"] = actor
    if action:
        q["action"] = {"$regex": "^" + re.escape(action)}

    total = db.audit.count_documents(q)
    entries = list(db.audit.find(q).sort("at", -1)
                   .skip((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
    return render_template(
        "admin/audit.html", entries=entries, total=total, page=page,
        pages=max(1, -(-total // PAGE_SIZE)), page_size=PAGE_SIZE,
        actors=sorted(x for x in db.audit.distinct("actor") if x),
        actions=sorted({(a or "").split(".")[0] for a in db.audit.distinct("action") if a}),
        filters={"actor": actor, "action": action})


@bp.route("/export/institution.xlsx")
@admin_required
def export_institution():
    buf = institution_excel(_year())
    audit(_actor(), "export.institution")
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-Repository-{_year()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export/<dept_code>.xlsx")
@admin_required
def export_department(dept_code):
    buf = department_excel(dept_code, _year())
    audit(_actor(), "export.department", dept_code)
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-{dept_code}-{_year()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export/<dept_code>.docx")
@admin_required
def export_department_word(dept_code):
    buf = submission_word(dept_code, _year())
    audit(_actor(), "export.word", dept_code)
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-Report-{dept_code}-{_year()}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")
