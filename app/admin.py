"""Office of Academics administration console."""

from __future__ import annotations

import io
from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, session, url_for)

from . import ugc_rules as U
from .auth import admin_required
from .db import audit, get_db, issue_department_login, now, rules_doc
from .exporter import (department_excel, institution_excel, submission_word)
from .importer import parse_workbook
from .schema import STAGE_BY_KEY, STAGES
from .workflow import (compute_status, department_analysis, get_or_create_submission,
                       institution_analysis, progress, stage_analysis, stage_board,
                       return_stage, stage_board, unlock_stage)

bp = Blueprint("admin", __name__)


def _year():
    from .db import settings
    return settings().get("academic_year") or current_app.config["ACADEMIC_YEAR"]


def _actor():
    return session["user"]["username"]


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

    return render_template("admin/dashboard.html", rows=rows, counts=counts,
                           by_campus=by_campus, stage_counts=stage_counts,
                           year=year, total=len(departments),
                           recent=list(db.audit.find().sort("at", -1).limit(12)))


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

@bp.route("/flow")
@admin_required
def flow():
    """The whole sequence in 3D: the four stages as platforms, every
    department standing at the stage it has reached, and — for a chosen
    department — its UG and PG programmes with their three parts."""
    return render_template("admin/flow.html", year=_year())


@bp.route("/flow.json")
@admin_required
def flow_data():
    from .schema import STAGE_KEYS
    from .workflow import part_status, programmes_of
    db = get_db()
    year = _year()
    departments = list(db.departments.find({"active": True}).sort("dept_name", 1))
    subs = {s["dept_code"]: s for s in db.submissions.find({"academic_year": year})}
    parts = next((s["parts"] for s in STAGES if s.get("parts")), [])
    out = []
    for d in departments:
        sub = subs.get(d["dept_code"]) or {}
        statuses = {k: compute_status(sub, k) for k in STAGE_KEYS}
        reached = next((i for i, k in enumerate(STAGE_KEYS)
                        if statuses[k] != "submitted"), len(STAGE_KEYS))
        progs = []
        for p in programmes_of(sub, d) if sub else []:
            progs.append({"code": p["programme_code"], "name": p["programme_name"],
                          "level": "PG" if p.get("level") in ("PG", "PGD") else "UG",
                          "parts": {k: part_status(sub, p["programme_code"], k)
                                    for k in parts}})
        out.append({"code": d["dept_code"], "name": d.get("dept_name", d["dept_code"]),
                    "campus": d.get("campus", ""), "school": d.get("school", ""),
                    "statuses": statuses, "reached": reached, "programmes": progs})
    return jsonify({
        "year": year,
        "stages": [{"key": s["key"], "title": s["title"], "group": s["group"]} for s in STAGES],
        "parts": [{"key": k, "title": STAGE_BY_KEY[k]["title"]} for k in parts],
        "departments": out,
    })


@bp.route("/analysis")
@admin_required
def analysis():
    """Every department in one reading: done, part-done, untouched, failing.

    The Office's standing question is "who still owes me what", and it used to
    be answered by opening departments one at a time. This answers it once.
    """
    db = get_db()
    year = _year()

    # Demonstration mode. Everything it needs lives in app/demo.py; delete that
    # module and this branch and the page is live-only.
    if request.args.get("demo") == "1":
        from .demo import demo_analysis
        rows, totals, stages = demo_analysis()
        return render_template("admin/analysis.html", rows=rows, totals=totals,
                               stages=stages, year=year, demo=True,
                               filters={"state": None, "q": ""})

    departments = list(db.departments.find({"active": True})
                       .sort([("place", 1), ("campus", 1), ("dept_name", 1)]))
    subs = {s["dept_code"]: s for s in db.submissions.find({"academic_year": year})}
    users = {u.get("dept_code"): u for u in db.users.find({"role": "department"})}

    rows = [department_analysis(d, subs.get(d["dept_code"]), users.get(d["dept_code"]))
            for d in departments]
    totals = institution_analysis(rows)
    stages = stage_analysis([stage_board(subs.get(d["dept_code"]) or {})
                             for d in departments])

    # filtering happens after the totals, so the summary always describes the
    # whole institution and not whatever slice is on screen
    state = request.args.get("state")
    search = (request.args.get("q") or "").strip().lower()
    if state:
        rows = [r for r in rows if r["state"] == state]
    if search:
        rows = [r for r in rows
                if search in (r["dept"].get("dept_name", "") + " "
                              + r["dept"].get("school", "") + " "
                              + r["dept"].get("dept_code", "")).lower()]

    return render_template("admin/analysis.html", rows=rows, totals=totals,
                           stages=stages, year=year, demo=False,
                           filters={"state": state, "q": search})


# ---------------------------------------------------------------------------
# department master
# ---------------------------------------------------------------------------

@bp.route("/departments")
@admin_required
def departments():
    db = get_db()
    q = {}
    place = request.args.get("place")
    campus = request.args.get("campus")
    school = request.args.get("school")
    search = (request.args.get("q") or "").strip()
    if place:
        q["place"] = place
    if campus:
        q["campus"] = campus
    if school:
        q["school"] = school
    if search:
        q["$or"] = [{"dept_name": {"$regex": search, "$options": "i"}},
                    {"dept_code": {"$regex": search, "$options": "i"}},
                    {"school": {"$regex": search, "$options": "i"}},
                    {"faculty": {"$regex": search, "$options": "i"}}]
    depts = list(db.departments.find(q)
                 .sort([("place", 1), ("campus", 1), ("school", 1), ("dept_name", 1)]))

    # only the campuses in the city being looked at: offering Kochi Campus
    # while Bangalore is selected would be a filter that can only return none
    campuses = [c for c in current_app.config["CAMPUSES"]
                if not place or db.departments.count_documents(
                    {"place": place, "campus": c})]
    return render_template("admin/departments.html", departments=depts,
                           schools=sorted(x for x in db.departments.distinct("school") if x),
                           campuses=campuses,
                           places=current_app.config["PLACES"],
                           total=db.departments.count_documents({}),
                           filters={"place": place, "campus": campus,
                                    "school": school, "q": search})


@bp.route("/departments/new", methods=["GET", "POST"])
@bp.route("/departments/<dept_code>/edit", methods=["GET", "POST"])
@admin_required
def department_form(dept_code=None):
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code}) if dept_code else None
    if dept_code and not dept:
        abort(404)

    # existing values offered as suggestions, so a new department lands in an
    # existing faculty and school rather than a near-miss spelling of one
    def _form(d):
        return render_template(
            "admin/department_form.html", dept=d,
            campuses=current_app.config["CAMPUSES"],
            places=current_app.config["PLACES"],
            faculties=sorted(x for x in db.departments.distinct("faculty") if x),
            schools=sorted(x for x in db.departments.distinct("school") if x))

    if request.method == "POST":
        f = request.form
        code = (f.get("dept_code") or "").strip().upper()
        if not code:
            flash("Department code is required.", "error")
            return _form(dept or f)
        clash = db.departments.find_one({"dept_code": code})
        if clash and (not dept or clash["_id"] != dept["_id"]):
            flash(f"Department code “{code}” is already in use.", "error")
            return _form(f)

        payload = {
            "dept_code": code,
            "dept_name": (f.get("dept_name") or "").strip(),
            "faculty": (f.get("faculty") or "").strip(),
            "school": (f.get("school") or "").strip(),
            "campus": f.get("campus") or current_app.config["CAMPUSES"][0],
            "place": f.get("place") or current_app.config["PLACES"][0],
            "active": f.get("active") == "on",
            "updated_at": now(),
        }
        if dept:
            db.departments.update_one({"_id": dept["_id"]}, {"$set": payload})
            audit(_actor(), "department.updated", code)
            flash(f"{payload['dept_name']} has been updated.", "success")
        else:
            payload["created_at"] = now()
            db.departments.insert_one(payload)
            audit(_actor(), "department.created", code)
            flash(f"{payload['dept_name']} has been added. "
                  f"Use “Issue every missing login” on the department list "
                  f"to give it one.", "success")
        return redirect(url_for("admin.departments"))

    return _form(dept)


@bp.route("/departments/<dept_code>/toggle", methods=["POST"])
@admin_required
def department_toggle(dept_code):
    db = get_db()
    d = db.departments.find_one({"dept_code": dept_code}) or abort(404)
    new = not d.get("active", True)
    db.departments.update_one({"_id": d["_id"]}, {"$set": {"active": new}})
    db.users.update_one({"dept_code": dept_code}, {"$set": {"active": new}})
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


@bp.route("/departments/clear", methods=["POST"])
@admin_required
def departments_clear():
    """Remove every department in one go, with its login and its submissions.

    This empties the master, so it asks for the word to be typed rather than
    for a button to be clicked. It is not as final as it sounds: seed.py puts
    the whole list back from the Office of Academics workbook.
    """
    db = get_db()
    if (request.form.get("confirm") or "").strip().upper() != "REMOVE ALL":
        flash("Nothing was removed — type REMOVE ALL to confirm.", "warning")
        return redirect(url_for("admin.departments"))

    counts = {
        "departments": db.departments.count_documents({}),
        "logins": db.users.count_documents({"role": "department"}),
        "submissions": db.submissions.count_documents({}),
    }
    db.departments.delete_many({})
    db.users.delete_many({"role": "department"})
    db.submissions.delete_many({})
    audit(_actor(), "departments.cleared", detail=counts)
    flash(f"Removed {counts['departments']} department(s), "
          f"{counts['logins']} login(s) and {counts['submissions']} submission(s). "
          f"Run seed.py to put the master back from the workbook.", "success")
    return redirect(url_for("admin.departments"))


@bp.route("/credentials/bulk", methods=["POST"])
@admin_required
def bulk_credentials():
    """Generate logins for every active department that has none."""
    db = get_db()
    made = 0
    for dept in list(db.departments.find({"active": True, "username": {"$exists": False}})):
        issue_department_login(db, dept, actor=_actor())
        made += 1
    audit(_actor(), "credentials.bulk", detail={"count": made})
    if made:
        flash(f"Issued a login for {made} department(s). The passwords are on "
              f"the credential sheet until each department signs in.", "success")
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
    default_campus = (request.form.get("default_campus")
                      or current_app.config["CAMPUSES"][0])
    default_place = (request.form.get("default_place")
                     or current_app.config["PLACES"][0])
    try:
        rows, meta = parse_workbook(data, sheet, default_campus=default_campus,
                                    default_place=default_place)
    except Exception as exc:
        flash(f"That file could not be read: {exc}", "error")
        return redirect(url_for("admin.import_departments"))

    db = get_db()
    existing = {d["dept_code"] for d in db.departments.find({}, {"dept_code": 1})}
    for r in rows:
        r["exists"] = r["dept_code"] in existing

    session["import_rows"] = rows[:500]
    return render_template("admin/import.html", preview=rows, meta=meta,
                           default_campus=default_campus,
                           default_place=default_place,
                           campuses=current_app.config["CAMPUSES"],
                           places=current_app.config["PLACES"])


@bp.route("/import/commit", methods=["POST"])
@admin_required
def import_commit():
    rows = session.pop("import_rows", None)
    if not rows:
        flash("The import preview expired. Upload the workbook again.", "error")
        return redirect(url_for("admin.import_departments"))

    chosen = set(request.form.getlist("include"))
    overwrite = request.form.get("overwrite") == "on"
    make_logins = request.form.get("make_logins") == "on"

    db = get_db()
    added = updated = skipped = logins = 0
    for r in rows:
        if r["dept_code"] not in chosen:
            continue
        existing = db.departments.find_one({"dept_code": r["dept_code"]})
        payload = {k: r[k] for k in
                   ("dept_name", "school", "dept_code", "campus")}
        if r.get("place"):
            payload["place"] = r["place"]
        if r.get("faculty"):
            payload["faculty"] = r["faculty"]
        payload["active"] = True
        payload["updated_at"] = now()
        if existing and not overwrite:
            skipped += 1
            continue
        if existing:
            db.departments.update_one({"_id": existing["_id"]}, {"$set": payload})
            updated += 1
        else:
            payload["created_at"] = now()
            db.departments.insert_one(payload)
            added += 1

        if make_logins:
            dept = db.departments.find_one({"dept_code": r["dept_code"]})
            if not dept.get("username"):
                issue_department_login(db, dept, actor=_actor())
                logins += 1

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
    depts = {d["dept_code"]: d for d in db.departments.find({"active": True})}
    subs = list(db.submissions.find({"academic_year": year}))
    rows = []
    for s in subs:
        d = depts.get(s["dept_code"])
        if not d:
            continue
        rows.append({"dept": d, "submission": s, "progress": progress(s),
                     "board": stage_board(s)})
    rows.sort(key=lambda r: -r["progress"]["percent"])
    return render_template("admin/submissions.html", rows=rows, year=year, stages=STAGES)


@bp.route("/submissions/<dept_code>")
@admin_required
def submission_detail(dept_code):
    db = get_db()
    year = _year()
    dept = db.departments.find_one({"dept_code": dept_code}) or abort(404)
    sub = get_or_create_submission(dept_code, year)
    return render_template("admin/submission_detail.html", dept=dept, submission=sub,
                           board=stage_board(sub), progress=progress(sub),
                           year=year, STAGE_BY_KEY=STAGE_BY_KEY)


@bp.route("/submissions/<dept_code>/<stage_key>/return", methods=["POST"])
@admin_required
def submission_return(dept_code, stage_key):
    note = (request.form.get("note") or "").strip()
    if not note:
        flash("Say what needs correcting before you send a stage back.", "error")
        return redirect(url_for("admin.submission_detail", dept_code=dept_code))
    return_stage(dept_code, _year(), stage_key, note, _actor())
    audit(_actor(), "stage.returned", f"{dept_code}/{stage_key}", {"note": note})
    flash(f"“{STAGE_BY_KEY[stage_key]['title']}” has been sent back for correction.", "info")
    return redirect(url_for("admin.submission_detail", dept_code=dept_code))


@bp.route("/submissions/<dept_code>/<stage_key>/unlock", methods=["POST"])
@admin_required
def submission_unlock(dept_code, stage_key):
    unlock_stage(dept_code, _year(), stage_key, _actor())
    audit(_actor(), "stage.unlocked", f"{dept_code}/{stage_key}")
    flash(f"“{STAGE_BY_KEY[stage_key]['title']}” has been opened for this department.", "info")
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
        table = []
        for row in doc.get("table2", U.DEFAULT_TABLE_2):
            key = row["key"]
            new = {"sl": row["sl"], "key": key, "label": row["label"]}
            for track in ("ug3", "ug4"):
                def val(suffix):
                    raw = request.form.get(f"{key}.{track}.{suffix}", "").strip()
                    return int(raw) if raw.isdigit() else None
                new[track] = {
                    "min": val("min") or 0,
                    "max": val("max"),
                    "applicable": request.form.get(f"{key}.{track}.applicable") == "on",
                }
            table.append(new)

        totals = {
            "ug3": int(request.form.get("total.ug3") or U.DEFAULT_TOTALS["ug3"]),
            "ug4": int(request.form.get("total.ug4") or U.DEFAULT_TOTALS["ug4"]),
        }
        other = dict(doc.get("other") or U.DEFAULT_OTHER_RULES)
        for k in ("marks_per_credit", "max_credits_per_course", "meeting_notice_days",
                  "revision_benchmark_threshold"):
            raw = request.form.get(f"other.{k}", "").strip()
            if raw.isdigit():
                other[k] = int(raw)

        db.rules.update_one({"_id": "ugc"},
                            {"$set": {"table2": table, "totals": totals, "other": other,
                                      "updated_at": now(), "updated_by": _actor()}})
        audit(_actor(), "rules.updated")
        flash("The credit rules have been updated. They apply to every validation from now on.",
              "success")
        return redirect(url_for("admin.rules"))

    return render_template("admin/rules.html", doc=doc, tracks=U.TRACKS,
                           defaults=U.DEFAULT_TABLE_2, in_lieu=U.IN_LIEU_RULE)


@bp.route("/rules/reset", methods=["POST"])
@admin_required
def rules_reset():
    get_db().rules.update_one({"_id": "ugc"},
                              {"$set": {"table2": U.DEFAULT_TABLE_2,
                                        "totals": U.DEFAULT_TOTALS,
                                        "other": U.DEFAULT_OTHER_RULES,
                                        "updated_at": now(), "updated_by": _actor()}})
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
    if request.method == "POST":
        from .db import settings as _s
        was_dev = bool(_s().get("dev_mode"))
        dev = request.form.get("dev_mode") == "on"
        db.settings.update_one(
            {"_id": "app"},
            {"$set": {"academic_year": (request.form.get("academic_year") or "").strip(),
                      "submissions_open": request.form.get("submissions_open") == "on",
                      "dev_mode": dev,
                      "banner": (request.form.get("banner") or "").strip(),
                      "updated_at": now()}})
        audit(_actor(), "settings.updated")
        # Unlocking every stage for every department is worth its own line in
        # the log, separate from whatever else was saved in the same form.
        if dev != was_dev:
            audit(_actor(), "settings.dev_mode." + ("on" if dev else "off"))
            flash("Developer mode is ON — every stage is unlocked for every "
                  "department." if dev else
                  "Developer mode is off. Stages lock in sequence again.",
                  "warning" if dev else "success")
        else:
            flash("Settings saved.", "success")
        return redirect(url_for("admin.app_settings"))
    from .db import settings as s
    return render_template("admin/settings.html", settings=s(),
                           stage_count=len(STAGES))


@bp.route("/audit")
@admin_required
def audit_log():
    entries = list(get_db().audit.find().sort("at", -1).limit(300))
    return render_template("admin/audit.html", entries=entries)


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
