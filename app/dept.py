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
from .db import settings as app_settings_doc
from .exporter import department_excel, submission_word
from .schema import STAGE_BY_KEY, STAGE_KEYS
from .notify import describe_changes
from .notify import record as notify_record
from .workflow import (OPENABLE, compute_status, get_or_create_submission,
                       grouped_board, next_action,
                       course_fill_source, form_data, part_status, prefill_for,
                       programme_fill_source, programme_stage_state, programmes_of,
                       progress, save_draft, stage_board, stage_state,
                       submit_stage, validate_only, batches, parts_for, revision_fill_source,
                       apply_defaults)

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
                           programmes=programmes_of(sub, dept), year=_year(),
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

    top_key = stage_def.get("parent") or stage_key
    status = compute_status(sub, stage_key)
    if status == "locked":
        prev = STAGE_BY_KEY[STAGE_KEYS[STAGE_KEYS.index(top_key) - 1]]["title"]
        flash(f"“{STAGE_BY_KEY[top_key]['title']}” opens once you have submitted “{prev}”.",
              "info")
        return redirect(url_for("dept.dashboard"))

    programme = None
    if stage_def.get("per_programme"):
        programmes = programmes_of(sub, dept)
        if not programmes:
            flash("Keep at least one programme in Department Information first.", "info")
            return redirect(url_for("dept.dashboard"))
        if stage_def.get("parts") or not programme_code:
            return _programme_hub(STAGE_BY_KEY[top_key], programmes, sub, dept)
        programme = next((p for p in programmes
                          if p.get("programme_code") == programme_code), None) or abort(404)
        state = programme_stage_state(sub, programme_code, stage_key)
        status = part_status(sub, programme_code, stage_key)
    else:
        state = stage_state(sub, stage_key)

    synced = False
    if programme:
        data = dict(state.get("data") or {})
        if status in OPENABLE:
            # a section the draft has never held opens with its prefill
            for key, value in prefill_for(stage_key, dept, _year(), programme, sub).items():
                data.setdefault(key, value)
        # read-only values follow the record they are copied from
        for key, vals in prefill_for(stage_key, dept, _year(), programme, sub,
                                     readonly_only=True).items():
            if isinstance(data.get(key), dict):
                data[key] = {**data[key], **vals}
    else:
        data, synced = form_data(stage_key, sub, dept, _year(), status in OPENABLE)

    credit_matrix = None
    if any(s.get("type") in ("credit_matrix", "credit_distribution")
           for s in stage_def["sections"]):
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

    # the arithmetic the form fills in by itself — the same figures the
    # server checks against
    other = U.DEFAULT_OTHER_RULES
    calc = {
        "weights": other["credit_from_hours"],
        "marks_per_credit": other["marks_per_credit"],
        "max_per_course": other["max_credits_per_course"],
        "nep_to_key": U.NEP_CATEGORY_TO_KEY,
        "required_total": (credit_matrix or {}).get("total"),
        # which semester 7-8 courses count: "honours", "research" or None
        "track": U.honours_track((programme or {}).get("degree_level")),
        # the UGC total for each degree, for Programme Information's credits
        "degree_totals": {d: (rules_doc().get("totals") or U.DEFAULT_TOTALS).get(t)
                          for d, t in U.DEGREE_TO_TRACK.items() if t},
    }

    fill = []
    if status in OPENABLE:
        if stage_key.startswith("prog_syllabus") and programme:
            fill = course_fill_source(sub, programme["programme_code"])
        elif stage_key == "prog_revision" and programme:
            fill = revision_fill_source(sub, programme["programme_code"])

    board = stage_board(sub)
    return render_template("dept/stage.html", calc=calc, fill=fill, stage=stage_def, dept=dept, submission=sub,
                           state=state, data=data, status=status, programme=programme,
                           credit_matrix=credit_matrix, year=_year(),
                           readonly=(status == "submitted"), synced=synced,
                           batch_tag=(batches()["current"] if stage_def.get("batch") == "current"
                                      else stage_def.get("batch") or ""),
                           parts=_parts_nav(sub, stage_def, programme),
                           prog_tree=_programme_tree(sub, dept, programme),
                           board=board, groups=grouped_board(board))


def _part_item(sub, code, k, s=None):
    """One part of a programme as the menus show it, with its batch tag."""
    d = STAGE_BY_KEY[k]
    tag = ""
    if d.get("batch") == "current":
        tag = batches(s)["current"]
    elif d.get("existing_batch"):
        tag = d["batch"]
    return {"key": k, "title": d["title"], "tag": tag,
            "existing": bool(d.get("existing_batch")), "optional": bool(d.get("optional")),
            "status": part_status(sub, code, k)}


def _programme_tree(sub, dept, current=None):
    """The side menu's Curriculum branch: UG / PG, each programme, its parts."""
    stage_def = next((s for s in STAGE_BY_KEY.values() if s.get("parts")), None)
    if not stage_def:
        return []
    here = (current or {}).get("programme_code")
    cfg = app_settings_doc()
    keys = parts_for(stage_def, cfg)
    levels = {"UG": [], "PG": []}
    for p in programmes_of(sub, dept):
        levels["PG" if p["level"] in ("PG", "PGD") else "UG"].append({
            "code": p["programme_code"], "name": p["programme_name"],
            "here": p["programme_code"] == here,
            "parts": [_part_item(sub, p["programme_code"], k, cfg) for k in keys],
        })
    tree = []
    for name, progs in levels.items():
        if progs:
            tree.append({"name": name, "programmes": progs,
                         "here": any(x["here"] for x in progs),
                         "done": sum(1 for x in progs
                                     if all(pt["status"] == "submitted" for pt in x["parts"]
                                            if not pt["optional"]))})
    return tree


def _parts_nav(sub, stage_def, programme):
    """Curriculum · Syllabus · Course Revision, as tabs across one programme."""
    if not programme or not stage_def.get("parent"):
        return []
    parent = STAGE_BY_KEY[stage_def["parent"]]
    cfg = app_settings_doc()
    return [dict(_part_item(sub, programme["programme_code"], k, cfg), here=k == stage_def["key"])
            for k in parts_for(parent, cfg)]


def _programme_hub(stage_def, programmes, sub, dept):
    """The Curriculum stage: the mapped programmes, UG and PG, three parts each."""
    groups = {}
    for p in programmes:
        p = dict(p)
        p["parts"] = []
        cfg = app_settings_doc()
        for k in parts_for(stage_def, cfg):
            st = programme_stage_state(sub, p["programme_code"], k)
            p["parts"].append(dict(_part_item(sub, p["programme_code"], k, cfg),
                                   errors=(st.get("summary") or {}).get("errors", 0),
                                   note=st.get("returned_note")))
        groups.setdefault("PG" if p["level"] in ("PG", "PGD") else "UG", []).append(p)
    board = stage_board(sub)
    return render_template("dept/choose_programme.html", stage=stage_def, groups=groups,
                           submission=sub, dept=dept, board=board,
                           groups_board=grouped_board(board),
                           status=compute_status(sub, stage_def["key"]))


# ---------------------------------------------------------------------------
# JSON endpoints used by the form renderer
# ---------------------------------------------------------------------------

def _guard(stage_key, programme_code=None):
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    stage_def = STAGE_BY_KEY.get(stage_key)
    closed = (jsonify({"ok": False, "error": "This stage is not open for editing."}), 409)
    if not stage_def or stage_def.get("parts"):
        return None, None, None, closed
    if stage_def.get("parent"):
        if (not programme_code or compute_status(sub, stage_key) == "locked"
                or part_status(sub, programme_code, stage_key) == "submitted"):
            return None, None, None, closed
    elif compute_status(sub, stage_key) not in OPENABLE:
        return None, None, None, closed
    programme = None
    if programme_code:
        programme = next((p for p in programmes_of(sub, dept)
                          if p.get("programme_code") == programme_code), None)
        if not programme:
            return None, None, None, (jsonify({"ok": False,
                                               "error": "Unknown programme."}), 404)
    return dept, sub, programme, None


def _pin_frozen(stage_key, data, dept, sub, programme):
    """A frozen section is whatever the Office's record says, whatever the
    page sent."""
    stage_def = STAGE_BY_KEY.get(stage_key) or {}
    frozen = [s["key"] for s in stage_def.get("sections", []) if s.get("frozen")]
    if frozen:
        pinned = prefill_for(stage_key, dept, _year(), programme, sub, readonly_only=True)
        for key in frozen:
            data[key] = pinned.get(key, {})
    return data


@bp.post("/api/<stage_key>/save")
@bp.post("/api/<stage_key>/<programme_code>/save")
@department_required
def api_save(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = _pin_frozen(stage_key, request.get_json(silent=True) or {}, dept, sub, programme)
    before = _stored_data(sub, stage_key, programme_code)
    save_draft(dept["dept_code"], _year(), stage_key, data, programme_code)
    _tell(dept, "saved", stage_key, programme, changes=describe_changes(stage_key, before, data))
    return jsonify({"ok": True, "saved_at": now().isoformat()})


def _stored_data(sub, stage_key, programme_code=None):
    if programme_code:
        return (((sub.get("programmes") or {}).get(programme_code) or {}).get(stage_key) or {}).get("data") or {}
    return ((sub.get("stages") or {}).get(stage_key) or {}).get("data") or {}


def _tell(dept, event, stage_key=None, programme=None, **kw):
    """An update for the Office; never in the way of the department's work."""
    try:
        notify_record(dept, event, stage_key=stage_key, programme=programme,
                      actor=_me()["username"], **kw)
    except Exception:
        current_app.logger.exception("Could not record an update")


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
    data = _pin_frozen(stage_key, request.get_json(silent=True) or {}, dept, sub, programme)
    before = _stored_data(sub, stage_key, programme_code)
    issues, summary, status = submit_stage(dept["dept_code"], _year(), stage_key, data,
                                           programme, _me()["username"])
    if status == "submitted":
        _tell(dept, "submitted", stage_key, programme,
              changes=describe_changes(stage_key, before, apply_defaults(stage_key, data)))
    if status == "submitted" and programme:
        audit(_me()["username"], "stage.submitted",
              f"{dept['dept_code']}/{programme['programme_code']}/{stage_key}")
        flash(f"{programme['programme_name']}: “{STAGE_BY_KEY[stage_key]['title']}” is submitted.",
              "success")
        return jsonify({"ok": True, "status": status, "issues": issues, "summary": summary,
                        "next": None,
                        "redirect": url_for("dept.stage",
                                            stage_key=STAGE_BY_KEY[stage_key]["parent"])})
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

    # does it carry the words a document for this box always has?
    from .keyword_match import check as keyword_check
    from .summarise import field_label
    match = keyword_check(folder / stored, field, field_label(stage_key, field))

    rec = {"dept_code": dept["dept_code"], "academic_year": _year(), "stage": stage_key,
           "field": field, "original_name": f.filename, "stored_name": stored,
           "size": size, "uploaded_by": _me()["username"], "uploaded_at": now(),
           "keyword_match": match}
    get_db().files.insert_one(rec)
    words = {"match": "keywords match", "weak": "few keywords match",
             "miss": "no expected keywords found", "unread": "no text to check"}[match["status"]]
    _tell(dept, "keyword_miss" if match["status"] == "miss" else "uploaded", stage_key,
          text=f"“{f.filename}” for {match['label']} — {words}"
               + (f" ({', '.join(match['found'])})" if match["found"] else ""))

    url = url_for("dept.download", stage_key=stage_key, stored=stored)
    return jsonify({
        "ok": True, "name": f.filename, "stored": stored, "size": size, "url": url,
        # drawn on the first request for it, then kept; the page falls back to
        # a card if it never arrives
        "thumb": url + "?thumb=1" if ext == ".pdf" else None,
        "match": match,
    })


# The browser renders a PDF or an image itself, but only if it is handed one
# inline; as an attachment it downloads instead. Anything else stays an
# attachment, because a browser asked to display a .docx offers to download
# it anyway — with a worse filename.
INLINE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
THUMB_MAX = (420, 560)


def _thumbnail(source: Path) -> Path | None:
    """Draw the first page of a PDF, once, and keep it beside the file.

    Returns the image's path, or None if it cannot be drawn — an encrypted
    PDF, a damaged one, or a deployment without the renderer installed. The
    caller falls back to the drawn card, so a failure here costs a picture
    and nothing else.
    """
    thumb = source.with_suffix(source.suffix + ".thumb.png")
    if thumb.exists():
        return thumb
    try:
        import pypdfium2 as pdfium
    except ImportError:          # renderer not installed on this deployment
        current_app.logger.info("No PDF renderer; previews fall back to a card.")
        return None
    from .pdflock import PDF_LOCK
    try:
        with PDF_LOCK:
            if thumb.exists():           # drawn by another request meanwhile
                return thumb
            doc = pdfium.PdfDocument(source)
            try:
                image = doc[0].render(scale=1.4).to_pil()
            finally:
                doc.close()
            image.thumbnail(THUMB_MAX)
            image.save(thumb, "PNG", optimize=True)
        return thumb
    except Exception:
        current_app.logger.warning("Could not draw a preview of %s", source.name)
        return None


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
    suffix = Path(rec["original_name"]).suffix.lower()

    if request.args.get("thumb") == "1":
        if suffix != ".pdf":
            abort(404)
        drawn = _thumbnail(path)
        if not drawn:
            abort(404)
        return send_file(drawn, mimetype="image/png", max_age=86400)

    inline = request.args.get("inline") == "1" and suffix in INLINE_EXT
    return send_file(path, as_attachment=not inline,
                     download_name=rec["original_name"])


@bp.post("/file/<stage_key>/<stored>/summary")
@department_required
def file_summary(stage_key, stored):
    """A short AI summary of an uploaded PDF, made once and kept."""
    from .summarise import SummaryError, summarise
    dept = _dept()
    rec = get_db().files.find_one({"dept_code": dept["dept_code"], "stored_name": stored})
    if not rec:
        return jsonify({"ok": False, "error": "That file was not found."}), 404
    path = (current_app.config["UPLOAD_ROOT"] / (rec.get("academic_year") or _year())
            / dept["dept_code"] / rec["stage"] / stored)
    try:
        out = summarise(rec, path, refresh=request.args.get("refresh") == "1")
    except SummaryError as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, **out})


# ---------------------------------------------------------------------------
# department's own exports
# ---------------------------------------------------------------------------

def _not_finished(dept):
    """The downloads are the finished record: until every stage is
    submitted, send the department back to its submission instead."""
    sub = get_or_create_submission(dept["dept_code"], _year())
    if sub.get("status") == "sealed":
        return None
    flash("The Excel and Word downloads appear once every stage is submitted.", "info")
    return redirect(url_for("dept.dashboard"))


@bp.route("/export.xlsx")
@department_required
def export_excel():
    dept = _dept()
    if (back := _not_finished(dept)):
        return back
    buf = department_excel(dept["dept_code"], _year())
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-{dept['dept_code']}-{_year()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export.docx")
@department_required
def export_word():
    dept = _dept()
    if (back := _not_finished(dept)):
        return back
    buf = submission_word(dept["dept_code"], _year())
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-Report-{dept['dept_code']}-{_year()}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")
