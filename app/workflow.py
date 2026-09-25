"""
Stage state machine.

A submission is one document per (department, academic year):

    {
      dept_code, academic_year,
      stages:     { <stage_key>: {status, data, issues, submitted_at, ...} },
      programmes: { <programme_code>: { <stage_key>: {status, data, issues, ...} } },
      status:     draft | in_progress | submitted | sealed
    }

Stage status values
    locked      previous stage not yet submitted — cannot be opened
    open        can be filled
    draft       partially filled, saved but not submitted
    submitted   submitted and validated clean; read-only for the department
    returned    the Office of Academics sent it back for correction
"""

from __future__ import annotations

from .db import get_db, now, rules_doc
from .schema import (PART_KEYS, STAGE_BY_KEY, STAGE_KEYS, STAGES, degree_years,
                     programme_level, stage_index)
from .validation import build_context, validate_stage

OPENABLE = {"open", "draft", "returned"}
DONE = {"submitted"}


def get_or_create_submission(dept_code: str, academic_year: str):
    db = get_db()
    doc = db.submissions.find_one({"dept_code": dept_code, "academic_year": academic_year})
    if doc:
        return doc
    doc = {
        "dept_code": dept_code,
        "academic_year": academic_year,
        "stages": {},
        "programmes": {},
        "status": "draft",
        "created_at": now(),
        "updated_at": now(),
    }
    db.submissions.insert_one(doc)
    return doc


def stage_state(submission: dict, stage_key: str) -> dict:
    return (submission.get("stages") or {}).get(stage_key) or {}


def programme_stage_state(submission: dict, programme_code: str, stage_key: str) -> dict:
    return (((submission.get("programmes") or {}).get(programme_code) or {})
            .get(stage_key) or {})


def compute_status(submission: dict, stage_key: str) -> str:
    """Resolve the live status of a stage, applying the sequential lock."""
    stage = STAGE_BY_KEY.get(stage_key) or {}
    if stage.get("parent"):
        return compute_status(submission, stage["parent"])

    stored = stage_state(submission, stage_key).get("status")
    if stage.get("parts"):
        # A container stage: its state is the state of its programme parts.
        if _gate(submission, stage_key) == "locked":
            return "locked"
        return parts_status(submission, stage)

    if stored in ("submitted", "returned", "draft"):
        return stored
    return _gate(submission, stage_key)


def _gate(submission, stage_key):
    """open when the stage before is submitted (or the admin forced it open)."""
    if stage_state(submission, stage_key).get("status") == "open":
        return "open"
    idx = stage_index(stage_key)
    if idx <= 0:
        return "open"
    prev = compute_status(submission, STAGE_KEYS[idx - 1])
    return "open" if prev in DONE else "locked"


def parts_status(submission: dict, stage: dict) -> str:
    """submitted once every part of every programme is submitted."""
    states = [programme_stage_state(submission, p["programme_code"], part).get("status")
              for p in programmes_of(submission) for part in stage["parts"]]
    if not states:
        return "open"
    if "returned" in states:
        return "returned"
    if all(s == "submitted" for s in states):
        return "submitted"
    if any(states):
        return "draft"
    return "open"


def part_status(submission: dict, programme_code: str, part_key: str) -> str:
    return programme_stage_state(submission, programme_code, part_key).get("status") or "open"


def stage_board(submission: dict):
    """The full stage list with live status, for the department dashboard."""
    board, unlocked_upto = [], True
    for s in STAGES:
        st = compute_status(submission, s["key"])
        state = stage_state(submission, s["key"])
        board.append({
            "key": s["key"],
            "title": s["title"],
            "group": s["group"],
            "blurb": s["blurb"],
            "per_programme": bool(s.get("per_programme")),
            "source_templates": s.get("source_templates") or [],
            "status": st,
            "can_open": st in OPENABLE,
            "errors": (state.get("summary") or {}).get("errors", 0),
            "warnings": (state.get("summary") or {}).get("warnings", 0),
            "submitted_at": state.get("submitted_at"),
            "returned_note": state.get("returned_note"),
        })
        if st not in DONE:
            unlocked_upto = False
    return board


def progress(submission: dict):
    done = sum(1 for s in STAGES if compute_status(submission, s["key"]) in DONE)
    return {"done": done, "total": len(STAGES),
            "percent": round(done * 100 / len(STAGES)) if STAGES else 0}


def programmes_of(submission: dict):
    """Programmes mapped to the department in Level 0, with derived details."""
    data = stage_state(submission, "dept_info").get("data") or {}
    out = []
    for p in data.get("programmes") or []:
        if not isinstance(p, dict) or not str(p.get("programme_code") or "").strip():
            continue
        p = dict(p)
        p["programme_code"] = str(p["programme_code"]).strip()
        years = degree_years(p.get("degree_level"))
        p["level"] = programme_level(p.get("degree_level"))
        p["duration_years"] = years
        p["semesters"] = years * 2 if years else None
        out.append(p)
    return out


def _ctx_for(submission, stage_key, programme=None):
    return build_context(submission, programme, rules_doc())


def save_draft(dept_code, academic_year, stage_key, data, programme_code=None):
    """Save without validating — used by autosave."""
    db = get_db()
    if programme_code:
        path = f"programmes.{programme_code}.{stage_key}"
    else:
        path = f"stages.{stage_key}"
    db.submissions.update_one(
        {"dept_code": dept_code, "academic_year": academic_year},
        {"$set": {f"{path}.data": data,
                  f"{path}.status": "draft",
                  f"{path}.updated_at": now(),
                  "updated_at": now(),
                  "status": "in_progress"}},
        upsert=True,
    )


def validate_only(submission, stage_key, data, programme=None):
    issues, summary = validate_stage(stage_key, data, _ctx_for(submission, stage_key, programme))
    return issues, summary


def submit_stage(dept_code, academic_year, stage_key, data, programme=None, actor=""):
    """Validate and, if clean, lock the stage and unlock the next one."""
    db = get_db()
    submission = get_or_create_submission(dept_code, academic_year)
    issues, summary = validate_stage(stage_key, data, _ctx_for(submission, stage_key, programme))

    programme_code = (programme or {}).get("programme_code")
    path = (f"programmes.{programme_code}.{stage_key}" if programme_code
            else f"stages.{stage_key}")

    status = "submitted" if summary["errors"] == 0 else "draft"
    update = {
        f"{path}.data": data,
        f"{path}.issues": issues,
        f"{path}.summary": summary,
        f"{path}.status": status,
        f"{path}.updated_at": now(),
        "updated_at": now(),
        "status": "in_progress",
    }
    if status == "submitted":
        update[f"{path}.submitted_at"] = now()
        update[f"{path}.submitted_by"] = actor
    db.submissions.update_one({"dept_code": dept_code, "academic_year": academic_year},
                              {"$set": update, "$unset": {f"{path}.returned_note": ""}})

    fresh = db.submissions.find_one({"dept_code": dept_code, "academic_year": academic_year})
    top = (STAGE_BY_KEY.get(stage_key) or {}).get("parent") or stage_key
    if (top == STAGE_KEYS[-1] and status == "submitted"
            and compute_status(fresh, top) == "submitted"):
        db.submissions.update_one({"_id": fresh["_id"]},
                                  {"$set": {"status": "sealed", "sealed_at": now()}})
    return issues, summary, status


def return_stage(dept_code, academic_year, stage_key, note, actor="", programme_code=None):
    """Office of Academics sends a submitted stage back for correction."""
    stage = STAGE_BY_KEY.get(stage_key) or {}
    if stage.get("parts"):
        # Send back every submitted part (or just one programme's).
        sub = get_or_create_submission(dept_code, academic_year)
        update = {"status": "in_progress", "updated_at": now()}
        for p in programmes_of(sub):
            code = p["programme_code"]
            if programme_code and code != programme_code:
                continue
            for part in stage["parts"]:
                if programme_stage_state(sub, code, part).get("status") == "submitted":
                    path = f"programmes.{code}.{part}"
                    update[f"{path}.status"] = "returned"
                    update[f"{path}.returned_note"] = note
                    update[f"{path}.returned_by"] = actor
                    update[f"{path}.returned_at"] = now()
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": update})
        return
    get_db().submissions.update_one(
        {"dept_code": dept_code, "academic_year": academic_year},
        {"$set": {f"stages.{stage_key}.status": "returned",
                  f"stages.{stage_key}.returned_note": note,
                  f"stages.{stage_key}.returned_by": actor,
                  f"stages.{stage_key}.returned_at": now(),
                  "status": "in_progress",
                  "updated_at": now()}})


def unlock_stage(dept_code, academic_year, stage_key, actor=""):
    """Admin override: force a stage open without submitting its predecessor."""
    get_db().submissions.update_one(
        {"dept_code": dept_code, "academic_year": academic_year},
        {"$set": {f"stages.{stage_key}.status": "open",
                  f"stages.{stage_key}.force_opened_by": actor,
                  f"stages.{stage_key}.force_opened_at": now(),
                  "updated_at": now()}}, upsert=True)


def prefill_source(department, academic_year, submission=None, programme=None):
    """Everything a prefill key can point at."""
    source = dict(department or {})
    source["academic_year"] = academic_year
    info = (stage_state(submission or {}, "dept_info").get("data") or {}).get("identity") or {}
    if info.get("dept_name"):
        source["dept_name"] = info["dept_name"]
    meeting = (stage_state(submission or {}, "bos_documents").get("data") or {}).get("meeting") or {}
    source["bos_date"] = meeting.get("bos_date")
    if programme:
        source.update({k: v for k, v in programme.items() if v not in (None, "")})
        source["specialisation"] = programme.get("specialisation") or "—"
        if programme.get("duration_years"):
            source["duration_months"] = programme["duration_years"] * 12
        source.setdefault("medium", "English")
        source.setdefault("programme_pattern", "Semester")
    return source


def prefill_for(stage_key, department, academic_year, submission=None, programme=None,
                readonly_only=False):
    """Values pulled from the department / programme record into a stage.

    With readonly_only, just the read-only fields — those are refreshed on every
    open so a renamed programme or a changed BoS date shows up everywhere."""
    stage = STAGE_BY_KEY.get(stage_key) or {}
    source = prefill_source(department, academic_year, submission, programme)
    out = {}
    for section in stage.get("sections", []):
        if section.get("type") != "fields":
            continue
        vals = {}
        for f in section.get("fields", []):
            if readonly_only and f.get("type") != "readonly":
                continue
            key = f.get("prefill")
            if key and source.get(key) not in (None, ""):
                vals[f["name"]] = source[key]
        if vals:
            out[section["key"]] = vals
    if stage_key == "prog_syllabus" and programme and not readonly_only:
        courses = programme_courses(submission, programme["programme_code"])
        if courses:
            out["courses"] = [{k: c[k] for k in ("course_code", "course_title", "credits",
                                                 "hours_per_week", "teaching_hours")}
                              for c in courses]
    return out


def programme_courses(submission, programme_code):
    """The courses in a programme's structure, with hours worked out."""
    data = programme_stage_state(submission or {}, programme_code, "prog_curriculum").get("data") or {}
    out = []
    for r in data.get("structure") or []:
        code = str(r.get("course_code") or "").strip()
        if not code:
            continue
        hours = 0
        for k in ("l", "t", "p", "e"):
            try:
                hours += int(float(r.get(k) or 0))
            except (TypeError, ValueError):
                pass
        out.append({"course_code": code, "course_title": r.get("course_title") or "",
                    "credits": r.get("credits"), "semester": r.get("semester"),
                    "hours_per_week": hours, "teaching_hours": hours * 15})
    return out
