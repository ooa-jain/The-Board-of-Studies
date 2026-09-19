"""Department-facing workflow: dashboard, stages, saving, validating, submitting."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, session, url_for)
from werkzeug.utils import secure_filename

from . import ugc_rules as U
from .auth import department_required
from .db import audit, get_db, now, rules_doc, settings
from .exporter import department_excel, submission_word
from .schema import STAGE_BY_KEY, STAGE_KEYS
from .workflow import (OPENABLE, compute_status, get_or_create_submission, next_action,
                       prefill_for, programme_stage_state, programmes_of,
                       progress, save_draft, stage_board, stage_state,
                       submit_stage, validate_only)

bp = Blueprint("dept", __name__)


def _me():
    return session["user"]


def _year():
    return settings().get("academic_year") or current_app.config["ACADEMIC_YEAR"]


def _dept():
    d = get_db().departments.find_one({"dept_code": _me()["dept_code"]})
    if not d or not d.get("active", True):
        abort(403)
    return d


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@bp.route("/")
@department_required
def dashboard():
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    return render_template("dept/dashboard.html", dept=dept, submission=sub,
                           board=stage_board(sub), progress=progress(sub),
                           programmes=programmes_of(sub), year=_year(),
                           next_step=next_action(sub))


# ---------------------------------------------------------------------------
# a stage
# ---------------------------------------------------------------------------

@bp.route("/stage/<stage_key>")
@bp.route("/stage/<stage_key>/<programme_code>")
@department_required
def stage(stage_key, programme_code=None):
    stage_def = STAGE_BY_KEY.get(stage_key) or abort(404)
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())

    status = compute_status(sub, stage_key)
    if status == "locked":
        prev = STAGE_BY_KEY[STAGE_KEYS[STAGE_KEYS.index(stage_key) - 1]]["title"]
        flash(f"“{stage_def['title']}” opens once you have submitted “{prev}”.", "info")
        return redirect(url_for("dept.dashboard"))

    programme = None
    if stage_def.get("per_programme"):
        programmes = programmes_of(sub)
        if not programmes:
            flash("Add your programmes in the Programme Information stage first.", "info")
            return redirect(url_for("dept.dashboard"))
        if not programme_code:
            return render_template("dept/choose_programme.html", stage=stage_def,
                                   programmes=programmes, submission=sub, dept=dept)
        programme = next((p for p in programmes
                          if p.get("programme_code") == programme_code), None) or abort(404)
        state = programme_stage_state(sub, programme_code, stage_key)
    else:
        state = stage_state(sub, stage_key)

    data = state.get("data") or {}
    if not data:
        data = prefill_for(stage_key, dept, _year())

    credit_matrix = None
    if any(s.get("type") == "credit_matrix" for s in stage_def["sections"]):
        doc = rules_doc()
        track = U.get_track((programme or {}).get("degree_level"))
        credit_matrix = {
            "track": track,
            "track_label": U.TRACKS.get(track, "Not a UG programme"),
            "rows": U.blank_credit_matrix(doc.get("table2") or U.DEFAULT_TABLE_2,
                                          track or "ug3",
                                          (programme or {}).get("degree_level")),
            "total": (doc.get("totals") or U.DEFAULT_TOTALS).get(track or "ug3"),
            "in_lieu": U.IN_LIEU_RULE,
            "needs_in_lieu": (programme or {}).get("degree_level") == U.HONOURS_NO_RESEARCH,
        }

    return render_template("dept/stage.html", stage=stage_def, dept=dept, submission=sub,
                           state=state, data=data, status=status, programme=programme,
                           credit_matrix=credit_matrix, year=_year(),
                           readonly=(status == "submitted"),
                           board=stage_board(sub))


# ---------------------------------------------------------------------------
# JSON endpoints used by the form renderer
# ---------------------------------------------------------------------------

def _guard(stage_key, programme_code=None):
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    if compute_status(sub, stage_key) not in OPENABLE:
        return None, None, None, (jsonify({"ok": False,
                                           "error": "This stage is not open for editing."}), 409)
    programme = None
    if programme_code:
        programme = next((p for p in programmes_of(sub)
                          if p.get("programme_code") == programme_code), None)
        if not programme:
            return None, None, None, (jsonify({"ok": False,
                                               "error": "Unknown programme."}), 404)
    return dept, sub, programme, None


@bp.post("/api/<stage_key>/save")
@bp.post("/api/<stage_key>/<programme_code>/save")
@department_required
def api_save(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    save_draft(dept["dept_code"], _year(), stage_key, data, programme_code)
    return jsonify({"ok": True, "saved_at": now().isoformat()})


@bp.post("/api/<stage_key>/validate")
@bp.post("/api/<stage_key>/<programme_code>/validate")
@department_required
def api_validate(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    issues, summary = validate_only(sub, stage_key, data, programme)
    return jsonify({"ok": True, "issues": issues, "summary": summary})


@bp.post("/api/<stage_key>/submit")
@bp.post("/api/<stage_key>/<programme_code>/submit")
@department_required
def api_submit(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    issues, summary, status = submit_stage(dept["dept_code"], _year(), stage_key, data,
                                           programme, _me()["username"])
    if status == "submitted":
        audit(_me()["username"], "stage.submitted", f"{dept['dept_code']}/{stage_key}")
        nxt_key = None
        i = STAGE_KEYS.index(stage_key)
        if i + 1 < len(STAGE_KEYS):
            nxt_key = STAGE_KEYS[i + 1]
        # Confirm on the page we send them to, rather than in a browser dialog,
        # and carry them straight into whatever is next instead of dropping
        # them back on the dashboard to find it themselves.
        stage_title = STAGE_BY_KEY[stage_key]["title"]
        nxt = next_action(get_or_create_submission(dept["dept_code"], _year()))
        if nxt:
            flash(f"“{stage_title}” is submitted. Next: “{nxt['title']}”.", "success")
            target = url_for("dept.stage", stage_key=nxt["key"])
        else:
            flash(f"“{stage_title}” is submitted. Your Board of Studies record is complete.",
                  "success")
            target = url_for("dept.dashboard")
        return jsonify({"ok": True, "status": status, "issues": issues, "summary": summary,
                        "next": {"key": nxt["key"], "title": nxt["title"]} if nxt else None,
                        "redirect": target})
    return jsonify({"ok": False, "status": status, "issues": issues, "summary": summary})


@bp.post("/api/upload")
@department_required
def api_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No file was received."}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in current_app.config["ALLOWED_UPLOAD_EXT"]:
        allowed = ", ".join(sorted(current_app.config["ALLOWED_UPLOAD_EXT"]))
        return jsonify({"ok": False,
                        "error": f"“{ext or 'that file type'}” is not accepted. "
                                 f"Allowed: {allowed}"}), 400

    dept = _dept()
    stage_key = request.form.get("stage") or "misc"
    field = request.form.get("field") or "file"

    folder = current_app.config["UPLOAD_ROOT"] / _year() / dept["dept_code"] / stage_key
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}-{secure_filename(f.filename)}"
    f.save(folder / stored)
    size = (folder / stored).stat().st_size

    rec = {"dept_code": dept["dept_code"], "academic_year": _year(), "stage": stage_key,
           "field": field, "original_name": f.filename, "stored_name": stored,
           "size": size, "uploaded_by": _me()["username"], "uploaded_at": now()}
    get_db().files.insert_one(rec)

    return jsonify({"ok": True, "name": f.filename, "stored": stored, "size": size,
                    "url": url_for("dept.download", stage_key=stage_key, stored=stored)})


@bp.route("/file/<stage_key>/<stored>")
@department_required
def download(stage_key, stored):
    dept = _dept()
    rec = get_db().files.find_one({"dept_code": dept["dept_code"], "stored_name": stored})
    if not rec:
        abort(404)
    path = current_app.config["UPLOAD_ROOT"] / _year() / dept["dept_code"] / stage_key / stored
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=rec["original_name"])


# ---------------------------------------------------------------------------
# department's own exports
# ---------------------------------------------------------------------------

@bp.route("/export.xlsx")
@department_required
def export_excel():
    dept = _dept()
    buf = department_excel(dept["dept_code"], _year())
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-{dept['dept_code']}-{_year()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export.docx")
@department_required
def export_word():
    dept = _dept()
    buf = submission_word(dept["dept_code"], _year())
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-Report-{dept['dept_code']}-{_year()}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")
