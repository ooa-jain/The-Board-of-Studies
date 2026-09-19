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
from .schema import STAGE_BY_KEY, STAGE_KEYS, STAGES, stage_index
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
    stored = stage_state(submission, stage_key).get("status")
    if stored in ("submitted", "returned", "draft"):
        return stored

    idx = stage_index(stage_key)
    if idx <= 0:
        return "open"

    prev_key = STAGE_KEYS[idx - 1]
    prev = compute_status(submission, prev_key)
    return "open" if prev in DONE else "locked"


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


def next_action(submission: dict):
    """The one stage a department should work on next, or None when done.

    A thirteen-stage sequence is easy to lose your place in, so the portal
    works this out rather than leaving it to the person. Order of urgency:
    a stage sent back for correction, then one already in progress, then the
    next one that has opened.
    """
    board = stage_board(submission)
    for wanted in ("returned", "draft", "open"):
        for s in board:
            if s["status"] == wanted:
                return s
    return None


def progress(submission: dict):
    done = sum(1 for s in STAGES if compute_status(submission, s["key"]) in DONE)
    return {"done": done, "total": len(STAGES),
            "percent": round(done * 100 / len(STAGES)) if STAGES else 0}


def programmes_of(submission: dict):
    """Programme rows captured in the Programme Information stage."""
    data = stage_state(submission, "ugc_programme").get("data") or {}
    return [p for p in (data.get("programmes") or []) if p.get("programme_code")]


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
    if stage_key == STAGE_KEYS[-1] and status == "submitted":
        db.submissions.update_one({"_id": fresh["_id"]},
                                  {"$set": {"status": "sealed", "sealed_at": now()}})
    return issues, summary, status


def return_stage(dept_code, academic_year, stage_key, note, actor=""):
    """Office of Academics sends a submitted stage back for correction."""
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


def prefill_for(stage_key, department, academic_year):
    """Values pulled from the department master into a stage's first render."""
    stage = STAGE_BY_KEY.get(stage_key) or {}
    source = dict(department or {})
    source["academic_year"] = academic_year
    out = {}
    for section in stage.get("sections", []):
        if section.get("type") != "fields":
            continue
        vals = {}
        for f in section.get("fields", []):
            key = f.get("prefill")
            if key and source.get(key) not in (None, ""):
                vals[f["name"]] = source[key]
        if vals:
            out[section["key"]] = vals
    return out
