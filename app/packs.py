"""
Department data packs — a department's existing BoS documents, already turned
into portal data, loaded in one step.

A pack is a JSON file in app/pack_data/ (built by a script in tools/packs/):

    {
      key, title,
      source:      {folder, folder_name, files[]},
      department:  {dept_code, dept_name, school, faculty, campus},
      programmes:  {<programme_code>: {programme_name, <part_key>: data}},
      attachments: [{file, programme, stage, section, field}]  files from
                   app/pack_data/files/<key>/ placed in a programme part's file box
      extra_files: [file]               files kept with the record, not in a box
      open_stages: [<stage_key>],      opened ahead of the sequential lock
      notes:       [str]               where the import departs from the source
    }

The department is matched to the master by name (and campus, if there are
several); it is created, with a login, only when it is not there. Each
programme part then goes through the normal submit path: a part that
validates clean is submitted, anything else is saved as a draft with its
issues, exactly as if the department had pressed Submit. Parts that already
hold data are left alone unless `replace` is set, and a submitted part is
never overwritten. Department Information is not touched: which catalogue
programmes run this year is the department's call.
"""

from __future__ import annotations

import json
import shutil
import uuid
from functools import lru_cache
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from . import catalogue
from .db import audit, get_db, issue_department_login, now
from .schema import STAGE_BY_KEY, degree_years, programme_level
from .workflow import (compute_status, get_or_create_submission, part_status,
                       prefill_for, programme_stage_state, programmes_of,
                       submit_stage, unlock_stage)

PACK_DIR = Path(__file__).resolve().parent / "pack_data"
FILES_DIR = PACK_DIR / "files"
PARTS = ("prog_curriculum", "prog_syllabus", "prog_revision")


@lru_cache(maxsize=None)
def _read(path: str, mtime: float):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def get_pack(key: str):
    path = PACK_DIR / f"{key}.json"
    if not path.is_file():
        return None
    return _read(str(path), path.stat().st_mtime)


def find_department(db, d):
    """The master record a pack belongs to: same name, the pack's campus if
    the name is on more than one campus."""
    name = catalogue._name(d["dept_name"])
    same = [x for x in db.departments.find({}) if catalogue._name(x.get("dept_name")) == name]
    if len(same) > 1:
        here = catalogue._places(d.get("campus"))
        same = [x for x in same if here & catalogue._places(x.get("campus"))] or same
    return same[0] if same else None


def available_packs():
    """Every pack, with the department it would fill and whether that has been done."""
    db = get_db()
    out = []
    for path in sorted(PACK_DIR.glob("*.json")):
        pack = get_pack(path.stem)
        dept = find_department(db, pack["department"])
        loaded = bool(dept and db.submissions.find_one(
            {"dept_code": dept["dept_code"], "imported_from.pack": pack["key"]}))
        out.append({"key": pack["key"], "title": pack["title"],
                    "department": dept or pack["department"], "exists": bool(dept),
                    "source": pack.get("source") or {},
                    "programmes": len(pack.get("programmes") or {}), "loaded": loaded})
    return out


def _merge(base: dict, extra: dict) -> dict:
    """Pack values over the prefill: field sections merge, tables replace."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (base or {}).items()}
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _with_degree(programme, data):
    """The programme as its Curriculum will describe it once saved."""
    level = ((data or {}).get("details") or {}).get("degree_level")
    if not level:
        return programme
    years = degree_years(level)
    return {**programme, "degree_level": level, "duration_years": years,
            "semesters": years * 2 if years else None, "level": programme_level(level)}


def _place(db, dept_code, academic_year, stage, field, src, actor):
    """Copy a pack file into the department's uploads, as if it had been uploaded."""
    folder = current_app.config["UPLOAD_ROOT"] / academic_year / dept_code / stage
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}-{secure_filename(src.name)}"
    shutil.copyfile(src, folder / stored)
    size = (folder / stored).stat().st_size
    db.files.insert_one({
        "dept_code": dept_code, "academic_year": academic_year, "stage": stage, "field": field,
        "original_name": src.name, "stored_name": stored, "size": size,
        "uploaded_by": actor, "uploaded_at": now(),
        # a file from the department's own folder, not a form to check
        "keyword_match": {"status": "unread", "label": field, "found": [], "expected": []},
    })
    return {"name": src.name, "stored": stored, "size": size,
            "url": f"/department/file/{stage}/{stored}", "thumb": None}


def _attach(db, pack, dept, academic_year, actor, sub_fn):
    """Put the pack's files where the department would have uploaded them.
    A box that already holds a file is left alone, so loading twice is safe."""
    code, folder = dept["dept_code"], FILES_DIR / pack["key"]
    attached, missing = [], []
    for att in pack.get("attachments") or []:
        src = folder / att["file"]
        if not src.is_file():
            missing.append(att["file"])
            continue
        sub = sub_fn()
        programme = next((p for p in programmes_of(sub, dept)
                          if p["programme_code"].upper() == att["programme"].upper()), None)
        if not programme:
            continue
        pcode = programme["programme_code"]
        state = programme_stage_state(sub, pcode, att["stage"])
        if state.get("status") == "submitted" or not state.get("data"):
            continue
        have = ((state["data"].get(att["section"]) or {}).get(att["field"]) or {})
        if isinstance(have, dict) and have.get("stored"):
            continue
        value = _place(db, code, academic_year, att["stage"], att["field"], src, actor)
        db.submissions.update_one(
            {"_id": sub["_id"]},
            {"$set": {f"programmes.{pcode}.{att['stage']}.data.{att['section']}.{att['field']}": value,
                      "updated_at": now()}})
        attached.append(att["file"])

    # files kept with the record as a whole (the checklist, the articulation sheets)
    sub = sub_fn()
    kept = {f["name"]: f for f in ((sub.get("imported_from") or {}).get("files") or [])}
    for name in pack.get("extra_files") or []:
        src = folder / name
        if name in kept:
            continue
        if not src.is_file():
            missing.append(name)
            continue
        kept[name] = _place(db, code, academic_year, "imported", "imported_file", src, actor)
        attached.append(name)
    return attached, missing, [kept[n] for n in kept]


def load_pack(key: str, academic_year: str, actor: str, replace: bool = False):
    """Load a pack. Returns what was created and where each part stands."""
    pack = get_pack(key)
    if not pack:
        raise KeyError(key)
    db = get_db()

    dept = find_department(db, pack["department"])
    created = dept is None
    if created:
        db.departments.insert_one({**pack["department"], "active": True,
                                   "created_at": now(), "updated_at": now()})
        dept = db.departments.find_one({"dept_code": pack["department"]["dept_code"]})
    code = dept["dept_code"]

    password = None
    if not dept.get("username") and not db.users.find_one({"dept_code": code,
                                                            "role": "department"}):
        _, password = issue_department_login(db, dept, actor=actor)
        dept = db.departments.find_one({"_id": dept["_id"]})

    def fresh():
        return get_or_create_submission(code, academic_year)

    for stage_key in pack.get("open_stages") or []:
        if compute_status(fresh(), stage_key, dev=False) == "locked":
            unlock_stage(code, academic_year, stage_key, actor=actor)

    written, skipped = [], []
    for prog_code, parts in (pack.get("programmes") or {}).items():
        programme = next((p for p in programmes_of(fresh(), dept)
                          if p["programme_code"].upper() == prog_code.upper()), None)
        if not programme:
            skipped.append(f"{prog_code} — not in the department's programmes offered")
            continue
        for part_key in PARTS:
            if part_key not in parts:
                continue
            sub = fresh()
            label = f"{prog_code} · {STAGE_BY_KEY[part_key]['title']}"
            state = programme_stage_state(sub, programme["programme_code"], part_key)
            if state.get("status") == "submitted" or (state.get("data") and not replace):
                skipped.append(f"{label} — already has data")
                continue
            if part_key == "prog_curriculum":
                programme = _with_degree(programme, parts[part_key])
            data = _merge(prefill_for(part_key, dept, academic_year, programme, sub),
                          parts[part_key])
            submit_stage(code, academic_year, part_key, data, programme=programme, actor=actor)
            written.append(label)

    attached, missing, kept = _attach(db, pack, dept, academic_year, actor, fresh)

    sub = fresh()
    db.submissions.update_one({"_id": sub["_id"]}, {"$set": {"imported_from": {
        "pack": key, "title": pack["title"], "source": pack.get("source") or {},
        "notes": pack.get("notes") or [], "by": actor, "at": now(),
        "files": kept, "files_missing": sorted(set(missing)),
    }}})
    audit(actor, "pack.loaded", code, {"pack": key, "written": len(written),
                                       "skipped": len(skipped), "created": created,
                                       "files": len(attached), "files_missing": len(set(missing))})
    return {"dept": dept, "created": created, "password": password,
            "written": written, "skipped": skipped, "attached": attached,
            "missing": sorted(set(missing)), "summary": status_summary(fresh(), dept)}


def status_summary(sub, dept):
    """Programme parts submitted, and parts saved as drafts."""
    done = draft = 0
    for p in programmes_of(sub, dept):
        for part in PARTS:
            st = part_status(sub, p["programme_code"], part)
            done += st == "submitted"
            draft += st in ("draft", "returned")
    return {"submitted": done, "draft": draft}
