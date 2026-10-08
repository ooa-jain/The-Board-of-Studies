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
from .report import ShareLinks
from .schema import STAGE_BY_KEY, STAGE_KEYS
from . import people
from .notify import describe_changes
from .notify import record as notify_record
from .workflow import (OPENABLE, compute_status, get_or_create_submission,
                       grouped_board, next_action,
                       course_fill_source, course_options, form_data, part_status, prefill_for,
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
# who is working on the shared login
# ---------------------------------------------------------------------------

_NO_ASK = {"dept.who", "dept.versions", "dept.version_restore"}
PERSON_COOKIE = "bos_person"


def _person_signer():
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="bos-person-v1")


def _remembered_person(dept_code):
    """The person this browser said it was, for this department, if it
    said so recently enough."""
    raw = request.cookies.get(PERSON_COOKIE)
    if not raw:
        return None
    try:
        days = current_app.config.get("PERSON_COOKIE_DAYS", 180)
        v = _person_signer().loads(raw, max_age=days * 86400)
    except Exception:
        return None
    if v.get("d") != dept_code or not v.get("n") or not v.get("e"):
        return None
    return {"name": v["n"], "email": v["e"]}


def _remember_person(resp, dept_code, person):
    days = current_app.config.get("PERSON_COOKIE_DAYS", 180)
    resp.set_cookie(PERSON_COOKIE, _person_signer().dumps({"d": dept_code, "n": person["name"],
                                                            "e": person["email"]}),
                    max_age=days * 86400, httponly=True, samesite="Lax",
                    secure=current_app.config.get("SESSION_COOKIE_SECURE", False))
    return resp


@bp.before_request
def _ask_who():
    """A department's login is shared, so each person says who they are once
    a session; their saves are kept under their name."""
    u = session.get("user") or {}
    if u.get("role") != "department":
        return None
    p = u.get("person")
    if not p:
        # this browser has said who it is before: no need to ask again
        p = _remembered_person(u.get("dept_code"))
        if p:
            u["person"] = p
            session["user"] = u
            session.modified = True
    if p:
        people.seen(u["dept_code"], p)
        return None
    if (not current_app.config.get("ASK_PERSON", True) or request.endpoint in _NO_ASK
            or request.method != "GET" or "/api/" in request.path):
        return None
    return redirect(url_for("dept.who", next=request.full_path.rstrip("?")))


@bp.route("/who", methods=["GET", "POST"])
@department_required
def who():
    dept = _dept()
    me = _me()
    nxt = request.values.get("next") or ""
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = url_for("dept.dashboard")
    error = None
    if request.method == "POST":
        name = " ".join((request.form.get("name") or "").split())[:80]
        email = (request.form.get("email") or "").strip().lower()[:120]
        if len(name) < 2:
            error = "Please give your name."
        elif "@" not in email or "." not in email.split("@")[-1] or " " in email:
            error = "Please give a working e-mail address."
        else:
            person = {"name": name, "email": email}
            me["person"] = person
            session["user"] = me
            session.modified = True
            people.seen(dept["dept_code"], person)
            audit(me["username"], "person.set", f"{name} <{email}>")
            return _remember_person(redirect(nxt), dept["dept_code"], person)
    return render_template("dept/who.html", dept=dept, nxt=nxt, error=error,
                           person=me.get("person"),
                           others=people.others_active(dept["dept_code"], me.get("person")),
                           known=people.known(dept["dept_code"]))


@bp.route("/versions")
@department_required
def versions():
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    rows = people.history(dept["dept_code"], _year())
    # what each version changed, against the one before it on the same stage
    by_part = {}
    for v in reversed(rows):
        k = (v["stage"], v["programme_code"])
        v["changes"] = describe_changes(v["stage"], by_part.get(k), v.get("data"))
        by_part[k] = v.get("data")
        v["title"] = STAGE_BY_KEY.get(v["stage"], {}).get("title", v["stage"])
        v["url"] = (url_for("dept.stage", stage_key=v["stage"], programme_code=v["programme_code"])
                    if v["programme_code"] else url_for("dept.stage", stage_key=v["stage"]))
        st = _part(sub, v["stage"], v["programme_code"]).get("status")
        v["locked"] = st in ("submitted", "approved")
        v["latest"] = False
    for k in by_part:
        newest = next(v for v in rows if (v["stage"], v["programme_code"]) == k)
        newest["latest"] = True
    return render_template("dept/versions.html", dept=dept, rows=rows, keep_days=people.KEEP_DAYS,
                           person=_person(), stage=request.args.get("stage"))


@bp.post("/versions/<vid>/restore")
@department_required
def version_restore(vid):
    from bson import ObjectId
    from bson.errors import InvalidId
    dept = _dept()
    try:
        v = get_db().versions.find_one({"_id": ObjectId(vid), "dept_code": dept["dept_code"],
                                        "academic_year": _year()})
    except InvalidId:
        v = None
    if not v:
        abort(404)
    sub = get_or_create_submission(dept["dept_code"], _year())
    code = v["programme_code"] or None
    if _part(sub, v["stage"], code).get("status") in ("submitted", "approved"):
        flash("That stage is submitted, so it cannot be changed. Ask the Office of Academic Affairs "
              "to send it back first.", "error")
        return redirect(url_for("dept.versions"))
    programme = None
    if code:
        programme = next((p for p in programmes_of(sub, dept) if p.get("programme_code") == code), None)
    before = _stored_data(sub, v["stage"], code)
    save_draft(dept["dept_code"], _year(), v["stage"], v.get("data") or {}, code)
    who_was = v.get("name") or "someone"
    people.keep(dept["dept_code"], _year(), v["stage"], code, v.get("data") or {}, _person(), kind="restore")
    _tell(dept, "saved", v["stage"], programme,
          changes=describe_changes(v["stage"], before, v.get("data") or {}))
    audit(_me()["username"], "version.restore", f"{v['stage']} {code or ''} from {v['at']}")
    flash(f"Restored the version {who_was} saved on {v['at'].strftime('%d %b, %H:%M')}.", "success")
    return redirect(url_for("dept.stage", stage_key=v["stage"], programme_code=code) if code
                    else url_for("dept.stage", stage_key=v["stage"]))


def _part(sub, stage_key, programme_code=None):
    if programme_code:
        return ((sub.get("programmes") or {}).get(programme_code) or {}).get(stage_key) or {}
    return (sub.get("stages") or {}).get(stage_key) or {}


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@bp.route("/")
@department_required
def dashboard():
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    open_comments = list(get_db().comments.find({"dept_code": dept["dept_code"], "academic_year": _year(),
                                                 "status": "open"}).sort("at", -1))
    for c in open_comments:
        c["url"] = (url_for("dept.stage", stage_key=c["stage"], programme_code=c["programme_code"])
                    if c.get("programme_code") else url_for("dept.stage", stage_key=c["stage"]))
        c["where"] = STAGE_BY_KEY.get(c["stage"], {}).get("title", c["stage"]) + \
            (f" · {c['programme_code']}" if c.get("programme_code") else "")
    from .autofill import pack_for
    drive = pack_for(get_db(), dept)
    # each programme's steps as a row of dots
    prog_rows, prog_heads = [], []
    for p in programmes_of(sub, dept):
        steps = _programme_steps(sub, p["programme_code"])
        prog_heads = prog_heads or [st["label"] + (" · current" if st["key"] == "prog_syllabus" else "")
                                    for st in steps]
        # an earlier batch not begun is optional, not overdue
        shown = [{**st, "status": "optional" if st["optional"] and st["status"] == "open" else st["status"]}
                 for st in steps]
        prog_rows.append({"code": p["programme_code"], "name": p["programme_name"], "level": p.get("level") or "",
                          "steps": shown, "url": steps[0]["url"] if steps else "#",
                          "done": all(st["status"] == "submitted" for st in steps if not st["optional"])})
    return render_template("dept/dashboard.html", dept=dept, submission=sub, open_comments=open_comments,
                           prog_rows=prog_rows, prog_heads=prog_heads,
                           drive=drive and {"title": drive["title"],
                                            "folder": (drive.get("source") or {}).get("folder"),
                                            "done": bool(sub.get("autofilled"))},
                           board=stage_board(sub), progress=progress(sub),
                           programmes=programmes_of(sub, dept), year=_year(),
                           next_step=next_action(sub), resume=_resume(sub, dept),
                           all_revisions_done=_all_revisions_done(sub, dept),
                           level_counts=_level_counts(prog_rows))


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

    syllabi = _syllabus_index(sub, stage_key, programme) if stage_key == "prog_curriculum" else []
    course_map, back = {}, None
    if programme and stage_key in ("prog_syllabus", "prog_revision"):
        # each course's semester and course group, from the programme structure
        cur = programme_stage_state(sub, programme["programme_code"], "prog_curriculum").get("data") or {}
        for r in cur.get("semester_structure") or []:
            r = r or {}
            for code, title in course_options(r.get("course_code"), r.get("course_title")):
                if code.upper() not in course_map:
                    course_map[code.upper()] = {"semester": r.get("semester"),
                                                "group": r.get("nep_category") or "",
                                                "title": title}
        back = url_for("dept.stage", stage_key="prog_curriculum",
                       programme_code=programme["programme_code"]) + "#sec-semester_structure"
    comments = list(get_db().comments.find({
        "dept_code": dept["dept_code"], "academic_year": _year(), "stage": stage_key,
        "programme_code": (programme or {}).get("programme_code", ""),
        "status": {"$in": ["open", "done"]}}).sort("at", -1))
    board = stage_board(sub)
    final, record = _final_step(sub, dept, stage_key, (programme or {}).get("programme_code"))
    step = next_step = None
    steps = []
    last_step = False
    if programme and stage_def.get("parent"):
        steps = _programme_steps(sub, programme["programme_code"])
        keys = [st["key"] for st in steps]
        if stage_key in keys:
            i = keys.index(stage_key)
            step = steps[i]
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            last_step = next_step is None
            if last_step:
                np_ = _next_programme(sub, dept, programme["programme_code"])
                next_step = np_ and {**np_, "label": "the next programme"}
    _note_place(dept, stage_key, (programme or {}).get("programme_code"))
    # a PG programme fills the PG Course Matrix: its own course groups and wording
    from .schema import for_level, pg_groups
    deg = ((data.get("details") or {}) if isinstance(data, dict) and isinstance(data.get("details"), dict)
           else {}).get("degree_level") or (programme or {}).get("degree_level")
    page_stage = for_level(stage_def, deg)
    if stage_key == "prog_curriculum":
        data = pg_groups(data, deg)
    return render_template("dept/stage.html", calc=calc, fill=fill, stage=page_stage, dept=dept, submission=sub,
                           final=final, record=record, syllabi=syllabi, comments=comments,
                           step=step, next_step=next_step, last_step=last_step, prog_steps=steps,
                           course_map=course_map, back_to_structure=back,
                           add_level=(request.args.get("add") if request.args.get("add") in ("UG", "PG")
                                      and stage_key == "dept_info" else ""),
                           back_to=(url_for("dept.stage", stage_key="curriculum")
                                    if request.args.get("back") == "curriculum"
                                    and stage_key == "dept_info" else ""),
                           state=state, data=data, status=status, programme=programme,
                           credit_matrix=credit_matrix, year=_year(),
                           readonly=(status == "submitted"), synced=synced,
                           batch_tag=(batches()["current"] if stage_def.get("batch") == "current"
                                      else stage_def.get("batch") or ""),
                           parts=_parts_nav(sub, stage_def, programme),
                           prog_tree=_programme_tree(sub, dept, programme),
                           all_revisions_done=_all_revisions_done(sub, dept),
                           suggest_phrases=_suggest_phrases(sub, dept),
                           board=board, groups=grouped_board(board))


@bp.route("/programmes/add")
@department_required
def add_programme():
    """From Curriculum: "add a new UG / PG programme". Department Information
    holds the programme list, so go there — reopened if it was already
    submitted — with a new row started, and come back to Curriculum after."""
    level = "PG" if request.args.get("level") == "PG" else "UG"
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    if sub.get("status") == "sealed":
        flash("This record is complete and sealed. Ask the Office of Academic Affairs to reopen "
              "Department Information before adding a programme.", "error")
        return redirect(url_for("dept.stage", stage_key="curriculum"))
    if stage_state(sub, "dept_info").get("status") == "submitted":
        get_db().submissions.update_one(
            {"dept_code": dept["dept_code"], "academic_year": _year()},
            {"$set": {"stages.dept_info.status": "draft", "updated_at": now()},
             "$unset": {"stages.dept_info.returned_note": ""}})
        audit(_me()["username"], "stage.reopened", f"{dept['dept_code']}/dept_info",
              {"why": f"add a new {level} programme"})
    return redirect(url_for("dept.stage", stage_key="dept_info", add=level, back="curriculum"))


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
        # the parts that count: the current batch (earlier batches are optional records)
        counted = [x for x in p["parts"] if not x["optional"]]
        p["done"] = sum(1 for x in counted if x["status"] == "submitted")
        p["total"] = len(counted)
        p["state"] = ("done" if p["done"] == p["total"] else
                      "returned" if any(x["status"] == "returned" for x in counted) else
                      "progress" if any(x["status"] in ("draft", "submitted") for x in counted) else "new")
        p["filled"] = sum(1 for x in counted if x["status"] in ("draft", "submitted"))
        p["url"] = url_for("dept.stage", stage_key=counted[0]["key"], programme_code=p["programme_code"])
        groups.setdefault("PG" if p["level"] in ("PG", "PGD") else "UG", []).append(p)
    board = stage_board(sub)
    level = request.args.get("level", "").upper()
    if level not in groups:
        level = "UG" if "UG" in groups else "PG"
    return render_template("dept/choose_programme.html", stage=stage_def, groups=groups, level=level,
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


def _syllabus_index(sub, stage_key, programme):
    """For a programme's Curriculum: every syllabus it has — the current
    batch's and each earlier batch's — with its courses' codes and titles,
    so each course row can say whether its syllabus is there and open it."""
    from .workflow import programme_stage_state
    if not programme:
        return []
    code = programme["programme_code"]
    out = []
    keys = [k for k in parts_for(STAGE_BY_KEY["curriculum"]) if k.startswith("prog_syllabus")]
    for k in keys:
        sd = STAGE_BY_KEY[k]
        data = programme_stage_state(sub, code, k).get("data") or {}
        courses = [{"code": str(r.get("course_code") or "").strip(),
                    "title": str(r.get("course_title") or "").strip()}
                   for r in (data.get("courses") or []) if isinstance(r, dict) and r.get("course_code")]
        out.append({"key": k, "current": k == "prog_syllabus",
                    "label": "Batch of " + batches()["current"] + " (current)" if k == "prog_syllabus"
                             else "Batch of " + (sd.get("batch") or ""),
                    "url": url_for("dept.stage", stage_key=k, programme_code=code),
                    "courses": courses})
    return out


def _final_step(sub, dept, stage_key, programme_code=None):
    """Whether submitting this stage completes the whole record — the one
    submit that opens the review — and the record, stage by stage and part
    by part, for that review."""
    from .workflow import programme_stage_state
    record, final = [], True
    progs = programmes_of(sub, dept)
    for k in STAGE_KEYS:
        sd = STAGE_BY_KEY[k]
        if sd.get("parts"):
            for p in progs:
                for part in sd["parts"]:
                    st = programme_stage_state(sub, p["programme_code"], part)
                    here = part == stage_key and p["programme_code"] == programme_code
                    record.append({"title": f"{p.get('programme_name') or p['programme_code']} · "
                                            f"{STAGE_BY_KEY[part]['title']}",
                                   "status": "now" if here else (st.get("status") or "open"),
                                   "at": st["submitted_at"].strftime("%d %b %Y") if st.get("submitted_at") else ""})
                    if not here and st.get("status") != "submitted":
                        final = False
            if not progs:
                final = False
            continue
        st = (sub.get("stages") or {}).get(k) or {}
        here = k == stage_key
        status = compute_status(sub, k)
        record.append({"title": sd["title"], "status": "now" if here else status,
                       "at": st["submitted_at"].strftime("%d %b %Y") if st.get("submitted_at") else ""})
        if not here and status != "submitted":
            final = False
    # an optional part (an earlier batch's syllabus) is never the final step
    if (STAGE_BY_KEY.get(stage_key) or {}).get("optional"):
        final = False
    return final, record


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
    people.keep(dept["dept_code"], _year(), stage_key, programme_code, data, _person())
    _tell(dept, "saved", stage_key, programme, changes=describe_changes(stage_key, before, data))
    return jsonify({"ok": True, "saved_at": now().isoformat()})


def _stored_data(sub, stage_key, programme_code=None):
    if programme_code:
        return (((sub.get("programmes") or {}).get(programme_code) or {}).get(stage_key) or {}).get("data") or {}
    return ((sub.get("stages") or {}).get(stage_key) or {}).get("data") or {}


def _person():
    return (session.get("user") or {}).get("person")


def _tell(dept, event, stage_key=None, programme=None, **kw):
    """An update for the Office; never in the way of the department's work."""
    p = _person()
    try:
        notify_record(dept, event, stage_key=stage_key, programme=programme,
                      actor=_me()["username"], person=(p or {}).get("name", ""), **kw)
    except Exception:
        current_app.logger.exception("Could not record an update")


@bp.post("/api/<stage_key>/sample")
@bp.post("/api/<stage_key>/<programme_code>/sample")
@department_required
def api_sample(stage_key, programme_code=None):
    """The demo department only: the sample answers for this stage."""
    from . import demo_dept
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    if not dept.get("demo"):
        abort(404)
    demo_dept.upload_samples(_year())          # anything removed comes back
    files = demo_dept._files_for(get_db(), _year())
    data = demo_dept.sample(stage_key, programme, files, _year())
    return jsonify({"ok": True, "data": _pin_frozen(stage_key, data, dept, sub, programme)})


@bp.post("/comments/<cid>/done")
@department_required
def comment_done(cid):
    """The department marks a comment from the Office as done, with a reply."""
    from bson import ObjectId
    dept = _dept()
    try:
        c = get_db().comments.find_one({"_id": ObjectId(cid), "dept_code": dept["dept_code"]})
    except Exception:
        c = None
    if not c:
        abort(404)
    reply = (request.form.get("reply") or "").strip()[:1000]
    get_db().comments.update_one({"_id": c["_id"]}, {"$set": {"status": "done", "reply": reply, "done_at": now()}})
    _tell(dept, "saved", c["stage"], None, changes=[{"section": "Comment from the Office", "field": c["text"][:60],
                                                     "before": "open", "after": "done" + (f": {reply[:60]}" if reply else "")}])
    flash("Thank you — the Office of Academic Affairs sees it is done.", "success")
    return redirect(request.referrer or url_for("dept.dashboard"))


@bp.post("/drive/fill")
@department_required
def drive_fill():
    """A department with a Drive data pack: fill every stage from it, and
    whatever the Drive folder did not cover with entries that suit."""
    from .autofill import fill_from_drive, pack_for
    dept = _dept()
    if not pack_for(get_db(), dept):
        abort(404)
    done = fill_from_drive(dept, _year(), (_person() or {}).get("name") or dept["dept_code"])
    sub = get_or_create_submission(dept["dept_code"], _year())
    for key, part in (sub.get("stages") or {}).items():
        if part.get("data"):
            people.keep(dept["dept_code"], _year(), key, None, part["data"], _person())
    # the Office sees it as an update, one per stage (the programmes under Curriculum)
    name = (_person() or {}).get("name", "")
    for key in STAGE_KEYS:
        parts = [d for d in done if d.startswith(STAGE_BY_KEY[key]["title"])] if key != "curriculum" \
            else [d for d in done if " · " in d]
        if parts:
            notify_record(dept, "saved", stage_key=key, person=name, actor=_me()["username"],
                          changes=[{"section": "Drive folder", "field": "Imported",
                                    "before": "", "after": f"{len(parts)} part{'s' if len(parts) != 1 else ''} filled from the Drive folder"}])
    flash(f"Data imported from your Drive folder into {len(done)} stages and programme parts. "
          "Anything the folder did not have is marked “to be confirmed” — add it manually during "
          "the relevant stage.", "success")
    return redirect(url_for("dept.dashboard"))


@bp.post("/demo/fill-all")
@department_required
def demo_fill_all():
    """The demo department only: every stage filled with sample answers."""
    from . import demo_dept
    dept = _dept()
    if not dept.get("demo"):
        abort(404)
    n = demo_dept.fill_all(_year())
    sub = get_or_create_submission(dept["dept_code"], _year())
    for key, part in (sub.get("stages") or {}).items():
        if part.get("data"):
            people.keep(dept["dept_code"], _year(), key, None, part["data"], _person())
    for code, parts in (sub.get("programmes") or {}).items():
        for key, part in (parts or {}).items():
            if isinstance(part, dict) and part.get("data"):
                people.keep(dept["dept_code"], _year(), key, code, part["data"], _person())
    flash(f"Filled {n} stage{'s' if n != 1 else ''} and programme parts with sample data. "
          "Open each in turn, press Submit, review and confirm.", "success")
    return redirect(url_for("dept.dashboard"))


def _template_issues(dept, stage_key, data):
    """A signed composition form with categories left blank cannot be
    submitted: one error per form, naming what to fill."""
    from .template_check import TEMPLATES, problems
    stage = STAGE_BY_KEY.get(stage_key) or {}
    out = []
    for sec in stage.get("sections", []):
        for f in sec.get("fields", []):
            if f.get("name") not in TEMPLATES:
                continue
            v = ((data or {}).get(sec["key"]) or {}).get(f["name"])
            if not isinstance(v, dict) or not v.get("stored"):
                continue
            rec = get_db().files.find_one({"dept_code": dept["dept_code"], "stored_name": v["stored"]})
            tpl = ((rec or {}).get("keyword_match") or {}).get("template")
            for msg in problems(tpl):
                out.append({"level": "error", "section": sec["key"], "field": f["name"],
                            "message": f"{f.get('label', f['name'])}: {msg}. Fill it in the form, "
                                       "sign it and upload it again."})
    return out


@bp.post("/api/<stage_key>/validate")
@bp.post("/api/<stage_key>/<programme_code>/validate")
@department_required
def api_validate(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    issues, summary = validate_only(sub, stage_key, data, programme)
    extra = _template_issues(dept, stage_key, data)
    if extra:
        issues = extra + issues
        summary = {**summary, "errors": summary.get("errors", 0) + len(extra)}
    return jsonify({"ok": True, "issues": issues, "summary": summary})


@bp.post("/api/<stage_key>/submit")
@bp.post("/api/<stage_key>/<programme_code>/submit")
@department_required
def api_submit(stage_key, programme_code=None):
    dept, sub, programme, bad = _guard(stage_key, programme_code)
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    res = _submit_one(dept, sub, stage_key, programme, data)
    if not res["ok"]:
        return jsonify(res)
    if programme:
        nxt = _next_part(dept, stage_key, programme_code)
        flash(f"{programme['programme_name']}: “{STAGE_BY_KEY[stage_key]['title']}” is submitted."
              + (f" Next: {nxt['title']}." if nxt else ""), "success")
        return jsonify({**res, "next": nxt,
                        "redirect": nxt["url"] if nxt else
                        url_for("dept.stage", stage_key=STAGE_BY_KEY[stage_key]["parent"])})
    stage_title = STAGE_BY_KEY[stage_key]["title"]
    if stage_key == "dept_info" and request.args.get("back") == "curriculum":
        flash(f"“{stage_title}” is submitted. The programme list is updated — "
              "your new programme is in Curriculum.", "success")
        return jsonify({**res, "next": None, "redirect": url_for("dept.stage", stage_key="curriculum")})
    nxt = next_action(get_or_create_submission(dept["dept_code"], _year()))
    if nxt:
        flash(f"“{stage_title}” is submitted. Next: “{nxt['title']}”.", "success")
        target = url_for("dept.stage", stage_key=nxt["key"])
    else:
        flash(f"“{stage_title}” is submitted. Your Board of Studies record is complete.", "success")
        target = url_for("dept.dashboard")
    return jsonify({**res, "next": {"key": nxt["key"], "title": nxt["title"]} if nxt else None,
                    "redirect": target})


def _submit_one(dept, sub, stage_key, programme, data):
    """Submit one stage or programme part: the form checks and the signed
    forms' blanks first, then submitted, told to the Office, logged."""
    programme_code = (programme or {}).get("programme_code")
    data = _pin_frozen(stage_key, data or {}, dept, sub, programme)
    blanks = _template_issues(dept, stage_key, data)
    if blanks:
        save_draft(dept["dept_code"], _year(), stage_key, data, programme_code)
        issues, summary = validate_only(sub, stage_key, data, programme)
        return {"ok": False, "status": "draft", "issues": blanks + issues,
                "summary": {**summary, "errors": summary.get("errors", 0) + len(blanks)}}
    before = _stored_data(sub, stage_key, programme_code)
    issues, summary, status = submit_stage(dept["dept_code"], _year(), stage_key, data,
                                           programme, _me()["username"])
    if status != "submitted":
        return {"ok": False, "status": status, "issues": issues, "summary": summary}
    _tell(dept, "submitted", stage_key, programme,
          changes=describe_changes(stage_key, before, apply_defaults(stage_key, data)))
    people.keep(dept["dept_code"], _year(), stage_key, programme_code, apply_defaults(stage_key, data),
                _person(), kind="submit")
    audit(_me()["username"], "stage.submitted",
          f"{dept['dept_code']}/{programme_code + '/' if programme_code else ''}{stage_key}")
    return {"ok": True, "status": status, "issues": issues, "summary": summary}


def _level_counts(rows):
    """UG and PG: how many programmes, how many complete."""
    out = []
    for lv in ("UG", "PG"):
        mine = [r for r in rows if (r["level"] or "").upper().startswith(lv)]
        if mine:
            out.append({"level": lv, "total": len(mine), "done": sum(1 for r in mine if r["done"])})
    return out


def _suggest_phrases(sub, dept):
    """Whole titles to offer while typing: every programme in the university's
    catalogue, and the course titles this department has already used."""
    from . import catalogue
    from .workflow import programme_stage_state
    out = [r.get("programme_name") for r in catalogue.load()]
    for p in programmes_of(sub, dept):
        code = p["programme_code"]
        out.append(p.get("programme_name"))
        cur = programme_stage_state(sub, code, "prog_curriculum").get("data") or {}
        out += [(r or {}).get("course_title") for r in cur.get("semester_structure") or [] if isinstance(r, dict)]
        syl = programme_stage_state(sub, code, "prog_syllabus").get("data") or {}
        out += [(r or {}).get("course_title") for r in syl.get("courses") or [] if isinstance(r, dict)]
    seen, phrases = set(), []
    for t in out:
        t = " ".join(str(t or "").split())
        # a cell may hold several titles: "Python / Python Lab"
        for one in [x.strip() for x in t.split(" / ")] if " / " in t else [t]:
            if 3 < len(one) < 200 and one.lower() not in seen:
                seen.add(one.lower())
                phrases.append(one)
    return phrases[:3000]


def _note_place(dept, stage_key, programme_code=None):
    """Where the department was last working, so its home can take it back
    there."""
    get_db().departments.update_one({"dept_code": dept["dept_code"]}, {"$set": {"last_place": {
        "year": _year(), "stage": stage_key, "programme_code": programme_code or "",
        "at": now(), "name": (_person() or {}).get("name", "")}}})


def _resume(sub, dept):
    """The place to continue from: where the department last was, or, if
    that is submitted, the next thing after it; with nowhere recorded, the
    next stage that needs work."""
    place = dept.get("last_place") or {}
    if place.get("year") == _year() and place.get("stage") in STAGE_BY_KEY:
        key, code = place["stage"], place.get("programme_code") or ""
        d = STAGE_BY_KEY[key]
        if code and d.get("parent"):
            label = f"{STAGE_BY_KEY[d['parent']]['title']} · {code} · {_step_label(key)}"
            if part_status(sub, code, key) == "submitted":
                nxt = _next_part(dept, key, code)
                if nxt:
                    return {"url": nxt["url"], "title": nxt["title"], "where": "next after " + label,
                            "at": place.get("at"), "name": place.get("name")}
            else:
                return {"url": url_for("dept.stage", stage_key=key, programme_code=code),
                        "title": label, "where": "where you left off",
                        "at": place.get("at"), "name": place.get("name")}
        elif not code and compute_status(sub, key) != "submitted":
            return {"url": url_for("dept.stage", stage_key=key), "title": d["title"],
                    "where": "where you left off", "at": place.get("at"), "name": place.get("name")}
    nxt = next_action(sub)
    if nxt:
        return {"url": url_for("dept.stage", stage_key=nxt["key"]), "title": nxt["title"],
                "where": "next to do", "at": None, "name": ""}
    return None


def _all_revisions_done(sub, dept):
    """Every programme's Course Revision submitted — the point at which the
    whole record can be reviewed and submitted."""
    progs = programmes_of(sub, dept)
    return bool(progs) and all(part_status(sub, p["programme_code"], "prog_revision") == "submitted"
                               for p in progs)


def _step_label(key, cfg=None):
    """A programme step as the buttons name it."""
    d = STAGE_BY_KEY[key]
    if key == "prog_curriculum":
        return "Curriculum"
    if key == "prog_syllabus":
        return f"Batch of {batches(cfg)['current']}".strip()
    if d.get("existing_batch"):
        return f"Batch of {d.get('batch', '')}".strip()
    if key == "prog_revision":
        return "Course Revision"
    return d["title"]


def _programme_steps(sub, code):
    """One programme's steps, in order: Curriculum, Current Batch, each
    earlier batch, Course Revision — with where each stands."""
    stage_def = next(s for s in STAGE_BY_KEY.values() if s.get("parts"))
    cfg = app_settings_doc()
    return [{"key": k, "label": _step_label(k, cfg), "status": part_status(sub, code, k),
             "optional": bool(STAGE_BY_KEY[k].get("optional")),
             "url": url_for("dept.stage", stage_key=k, programme_code=code)}
            for k in parts_for(stage_def, cfg)]


def _next_programme(sub, dept, code):
    """The programme after this one that still has something to submit."""
    progs = [p["programme_code"] for p in programmes_of(sub, dept)]
    here = progs.index(code) if code in progs else -1
    for c in progs[here + 1:] + progs[:max(here, 0)]:
        for st in _programme_steps(sub, c):
            if st["status"] != "submitted" and not st["optional"]:
                return st
    return None


def _next_part(dept, stage_key, programme_code):
    """After a programme part: the next step of the same programme not yet
    submitted (Curriculum → Current Batch → an earlier batch it has begun →
    Revision), then the programmes after it, then any left before it."""
    sub = get_or_create_submission(dept["dept_code"], _year())
    steps = _programme_steps(sub, programme_code)
    keys = [st["key"] for st in steps]
    here = keys.index(stage_key) if stage_key in keys else -1
    for st in steps[here + 1:]:
        if st["status"] != "submitted":
            return {"key": st["key"], "title": st["label"], "url": st["url"]}
    nxt = _next_programme(sub, dept, programme_code)
    if nxt:
        return {"key": nxt["key"], "title": nxt["label"], "url": nxt["url"]}
    return None


def _record_items(sub, dept):
    """Every stage and programme part, in the order they are filled, with
    what is in it — for the review of the whole record."""
    from .workflow import programme_stage_state
    items = []
    for k in STAGE_KEYS:
        sd = STAGE_BY_KEY[k]
        if sd.get("parts"):
            for p in programmes_of(sub, dept):
                code = p["programme_code"]
                for part in parts_for(sd):
                    pd = STAGE_BY_KEY[part]
                    st = programme_stage_state(sub, code, part)
                    optional = bool(pd.get("optional"))
                    if optional and not st.get("data"):
                        continue
                    title = pd["title"]
                    items.append({"key": part, "programme": code,
                                  "title": f"{p.get('programme_name') or code} · {title}",
                                  "group": sd.get("group", ""), "optional": optional,
                                  "status": st.get("status") or "open",
                                  "url": url_for("dept.stage", stage_key=part, programme_code=code),
                                  "stage": {"title": pd["title"], "sections": pd.get("sections", [])},
                                  "data": st.get("data") or {}})
            continue
        st = (sub.get("stages") or {}).get(k) or {}
        items.append({"key": k, "programme": "", "title": sd["title"], "group": sd.get("group", ""),
                      "optional": False, "status": compute_status(sub, k),
                      "url": url_for("dept.stage", stage_key=k),
                      "stage": {"title": sd["title"], "sections": sd.get("sections", [])},
                      "data": st.get("data") or {}})
    return items


@bp.route("/api/record")
@department_required
def api_record():
    """The whole record, for “Review & submit all”."""
    dept = _dept()
    sub = get_or_create_submission(dept["dept_code"], _year())
    items = _record_items(sub, dept)
    only = request.args.get("programme")
    name = dept.get("dept_name", "")
    if only:
        # one programme's own review: its parts, earlier batches it has begun included
        items = [{**i, "title": _step_label(i["key"])} for i in items if i["programme"] == only]
        name = next((p.get("programme_name") for p in programmes_of(sub, dept)
                     if p["programme_code"] == only), only)
    return jsonify({"ok": True, "dept_name": name, "items": items})


@bp.post("/api/submit-all")
@department_required
def api_submit_all():
    """Submit every stage and programme part not yet submitted, in order,
    as saved. Stops at the first that cannot go, and says which and why."""
    dept = _dept()
    done = []
    only = request.args.get("programme")
    sub = get_or_create_submission(dept["dept_code"], _year())
    for item in _record_items(sub, dept):
        if only and item["programme"] != only:
            continue
        if item["status"] == "submitted":
            continue
        sub = get_or_create_submission(dept["dept_code"], _year())
        programme = None
        if item["programme"]:
            programme = next((p for p in programmes_of(sub, dept)
                              if p.get("programme_code") == item["programme"]), None)
        if not item["data"]:
            return jsonify({"ok": False, "done": done,
                            "failed": {"title": item["title"], "url": item["url"],
                                       "issues": [{"level": "error", "message": "Nothing has been filled in here yet."}]}})
        if compute_status(sub, item["key"] if not item["programme"] else STAGE_BY_KEY[item["key"]]["parent"]) == "locked":
            return jsonify({"ok": False, "done": done,
                            "failed": {"title": item["title"], "url": item["url"],
                                       "issues": [{"level": "error", "message": "This stage is still locked."}]}})
        res = _submit_one(dept, sub, item["key"], programme, item["data"])
        if not res["ok"]:
            return jsonify({"ok": False, "done": done,
                            "failed": {"title": item["title"], "url": item["url"],
                                       "issues": [i for i in res.get("issues", []) if i.get("level") == "error"][:8]}})
        done.append(item["title"])
    if only:
        sub = get_or_create_submission(dept["dept_code"], _year())
        nxt = _next_programme(sub, dept, only)
        if done:
            flash(f"This programme is submitted — {len(done)} part{'s' if len(done) != 1 else ''}."
                  + (" On to the next programme." if nxt else ""), "success")
        return jsonify({"ok": True, "done": done,
                        "redirect": nxt["url"] if nxt else url_for("dept.stage", stage_key="curriculum")})
    if done:
        flash(f"Submitted {len(done)} stage{'s' if len(done) != 1 else ''} and parts. "
              "Your Board of Studies record is with the Office of Academic Affairs.", "success")
    return jsonify({"ok": True, "done": done, "redirect": url_for("dept.dashboard")})


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
               + (f" ({', '.join(match.get('seen') or match['found'])})" if match["found"] else ""))

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
    buf = department_excel(dept["dept_code"], _year(), ShareLinks(dept["dept_code"], _year()))
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-{dept['dept_code']}-{_year()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export.docx")
@department_required
def export_word():
    dept = _dept()
    if (back := _not_finished(dept)):
        return back
    buf = submission_word(dept["dept_code"], _year(), ShareLinks(dept["dept_code"], _year()))
    return send_file(buf, as_attachment=True,
                     download_name=f"BoS-Report-{dept['dept_code']}-{_year()}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")
