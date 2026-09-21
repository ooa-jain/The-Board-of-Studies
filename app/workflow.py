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

from .db import get_db, now, rules_doc, settings
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


def dev_mode() -> bool:
    """Is the sequential lock switched off?

    Developer mode opens every stage of every department at once, so the
    portal can be walked through, shown or tested without filing twelve
    stages to reach the thirteenth. It is a view of the same data, not a
    different one: nothing is written differently while it is on, and a
    stage filled during it stays filled after it goes off.
    """
    try:
        from flask import g
        # Cached for the request. The analysis screen builds a board for every
        # department in the institution; without this, each one would go back
        # to the database to ask the same question.
        if not hasattr(g, "_dev_mode"):
            g._dev_mode = bool(settings().get("dev_mode"))
        return g._dev_mode
    except Exception:
        # Called with no application context — a script, or a test
        # exercising these functions directly. The lock is the safe answer.
        return False


def compute_status(submission: dict, stage_key: str, dev: bool | None = None) -> str:
    """Resolve the live status of a stage, applying the sequential lock.

    `dev` is the developer-mode flag. Leave it None and it is looked up;
    pass it when resolving a whole board, so thirteen stages cost one
    lookup rather than thirteen.
    """
    stored = stage_state(submission, stage_key).get("status")
    if stored in ("submitted", "returned", "draft"):
        return stored

    idx = stage_index(stage_key)
    if idx <= 0:
        return "open"

    # Developer mode lifts the lock and nothing else. A stage that has been
    # submitted or sent back kept that status above and never reaches here.
    if dev_mode() if dev is None else dev:
        return "open"

    prev_key = STAGE_KEYS[idx - 1]
    prev = compute_status(submission, prev_key, dev)
    return "open" if prev in DONE else "locked"


def stage_board(submission: dict, dev: bool | None = None):
    """The full stage list with live status, for the department dashboard."""
    if dev is None:
        dev = dev_mode()
    board, unlocked_upto = [], True
    for s in STAGES:
        st = compute_status(submission, s["key"], dev)
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


def grouped_board(board):
    """The same stage list, folded into its groups.

    Thirteen stages read as thirteen unrelated errands when they are listed
    flat. Grouped, the side menu can say which ones belong together, how many
    of each group are done, and which group you are working inside.

    The key is "stages" rather than "items": a template asking a dict for
    .items gets the dict's own method, silently, and renders nothing.
    """
    groups = []
    for s in board:
        if not groups or groups[-1]["name"] != s["group"]:
            groups.append({"name": s["group"], "stages": []})
        groups[-1]["stages"].append(s)

    for g in groups:
        g["total"] = len(g["stages"])
        g["done"] = sum(1 for s in g["stages"] if s["status"] in DONE)
        g["complete"] = g["done"] == g["total"]
    return groups


def department_analysis(dept, submission, user=None):
    """Where one department stands, as one row.

    Everything the Office asks about a department — has it started, how far
    has it got, is a stage half-filled, has anyone even signed in, is anything
    failing validation — answered from the submission rather than from a
    conversation.
    """
    board = stage_board(submission or {})
    by_status = {}
    for s in board:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1

    done = by_status.get("submitted", 0)
    total = len(board)
    errors = sum(s["errors"] for s in board)
    warnings = sum(s["warnings"] for s in board)

    # A stage that is a draft has been opened and left part-filled; that is a
    # different thing from one nobody has touched, and the Office chases them
    # differently.
    half = by_status.get("draft", 0)
    returned = by_status.get("returned", 0)

    signed_in = bool((user or {}).get("last_login"))
    # The user record is what decides whether a login exists; the department's
    # own `username` field is a copy of it, and a copy can be missing.
    has_login = bool(user) or bool(dept.get("username"))

    if not has_login:
        state, label = "no_login", "No login issued"
    elif not signed_in:
        state, label = "never_in", "Never signed in"
    elif done == total and total:
        state, label = "complete", "All stages submitted"
    elif returned:
        state, label = "returned", "Sent back for correction"
    elif done or half:
        state, label = "in_progress", "In progress"
    else:
        state, label = "not_started", "Signed in, nothing filed"

    nxt = next_action(submission or {})
    return {
        "dept": dept,
        "state": state,
        "label": label,
        "done": done,
        "total": total,
        "percent": round(done * 100 / total) if total else 0,
        "half": half,
        "returned": returned,
        "locked": by_status.get("locked", 0),
        "open": by_status.get("open", 0),
        "errors": errors,
        "warnings": warnings,
        "next": nxt,
        "has_login": has_login,
        "signed_in": signed_in,
        "last_login": (user or {}).get("last_login"),
        "updated_at": (submission or {}).get("updated_at"),
        "sealed": (submission or {}).get("status") == "sealed",
    }


def institution_analysis(rows):
    """The totals across every department, from the rows themselves.

    Counted here rather than re-queried, so the summary can never disagree
    with the table underneath it.
    """
    totals = {
        "departments": len(rows),
        "complete": 0, "in_progress": 0, "not_started": 0,
        "returned": 0, "never_in": 0, "no_login": 0,
        "stages_done": 0, "stages_total": 0,
        "half_filled": 0, "errors": 0, "warnings": 0,
        "sealed": 0,
    }
    for r in rows:
        totals[r["state"]] = totals.get(r["state"], 0) + 1
        totals["stages_done"] += r["done"]
        totals["stages_total"] += r["total"]
        totals["half_filled"] += r["half"]
        totals["errors"] += r["errors"]
        totals["warnings"] += r["warnings"]
        totals["sealed"] += 1 if r["sealed"] else 0

    totals["percent"] = (round(totals["stages_done"] * 100 / totals["stages_total"])
                         if totals["stages_total"] else 0)
    totals["with_errors"] = sum(1 for r in rows if r["errors"])
    totals["untouched"] = totals["not_started"] + totals["never_in"] + totals["no_login"]
    return totals


def stage_analysis(rows_of_boards):
    """How far the whole institution has got, stage by stage."""
    out = []
    for i, stage in enumerate(STAGES):
        tally = {"submitted": 0, "draft": 0, "returned": 0, "open": 0, "locked": 0}
        for board in rows_of_boards:
            st = board[i]["status"]
            tally[st] = tally.get(st, 0) + 1
        total = max(1, len(rows_of_boards))
        out.append({
            "key": stage["key"], "title": stage["title"], "group": stage["group"],
            "n": i + 1, **tally,
            "percent": round(tally["submitted"] * 100 / total),
        })
    return out


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
