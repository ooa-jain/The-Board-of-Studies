"""
One department's record as a single report — what the Excel and Word
downloads print, top to bottom on one sheet:

    the department, the stages and what each holds (✓ filled, ✗ not yet,
    with every uploaded document as a link that opens it on the portal),
    then the UG and PG programmes, each with its parts and a link to the
    programme's own report page.

`links` turns a file or a programme into a URL. The admin downloads link to
the admin pages, a department's own download to its pages, and with no
links (a script) the names are printed without them.
"""

from __future__ import annotations

from datetime import datetime

from .schema import STAGE_BY_KEY, STAGES
from .workflow import compute_status, part_status, prefill_for, programmes_of, progress

STATUS_WORDS = {"submitted": "✓ Submitted", "draft": "In progress", "returned": "Returned",
                "open": "Not started", "locked": "Locked"}
PARTS = ("prog_curriculum", "prog_syllabus", "prog_revision")


class NoLinks:
    def file(self, stage, value):
        return None

    def programme(self, code):
        return None


_VIEWABLE = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif")


def _inline(value):
    # a PDF or a picture opens in the browser tab; anything else downloads
    return 1 if str(value.get("name", "")).lower().endswith(_VIEWABLE) else None


class AdminLinks:
    """Links for the Office's downloads: documents and programme reports on the admin side."""

    def __init__(self, dept_code):
        self.dept_code = dept_code

    def file(self, stage, value):
        from flask import url_for
        return url_for("admin.document", dept_code=self.dept_code, stored=value["stored"],
                       inline=_inline(value), _external=True)

    def programme(self, code):
        from flask import url_for
        return url_for("admin.programme_report", dept_code=self.dept_code,
                       programme_code=code, _external=True)


class DeptLinks:
    """Links for a department's own download: its files and its programme pages."""

    def file(self, stage, value):
        from flask import url_for
        return url_for("dept.download", stage_key=stage, stored=value["stored"],
                       inline=_inline(value), _external=True)

    def programme(self, code):
        from flask import url_for
        return url_for("dept.stage", stage_key="prog_curriculum", programme_code=code,
                       _external=True)


def _blank(v):
    return v is None or v == "" or v == [] or v == {} or (isinstance(v, str) and not v.strip())


def files_in(value):
    """The uploaded files in a field's value: one, several, or none."""
    if isinstance(value, dict) and value.get("stored"):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict) and v.get("stored")]
    return []


def _text(v, limit=240):
    if _blank(v):
        return ""
    if isinstance(v, (list, tuple)):
        s = "; ".join(_text(x, limit) for x in v if not _blank(x))
    elif isinstance(v, dict):
        s = "; ".join(f"{k}: {_text(x, limit)}" for k, x in v.items() if not _blank(x))
    elif isinstance(v, datetime):
        s = v.strftime("%d %b %Y")
    else:
        s = str(v)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit - 1] + "…"


def section_items(stage_key, data, links):
    """What one stage or part holds, field by field: (filled, label, text, [(name, url)])."""
    items = []
    for section in (STAGE_BY_KEY.get(stage_key) or {}).get("sections", []):
        payload = (data or {}).get(section["key"])
        kind = section.get("type", "fields")
        if kind == "fields":
            vals = payload if isinstance(payload, dict) else {}
            for f in section.get("fields", []):
                if f.get("type") == "fixed" or f.get("hidden"):
                    continue
                v = vals.get(f["name"])
                docs = [(x.get("name") or "file", links.file(stage_key, x)) for x in files_in(v)]
                text = "" if docs else _text(v)
                if not f.get("required") and not docs and not text:
                    continue                      # an optional box left empty says nothing
                items.append((bool(docs or text), f.get("label") or f["name"], text, docs))
        elif kind == "programme_list":
            rows = payload if isinstance(payload, list) else []
            kept = [r for r in rows if r.get("decision") != "remove"]
            items.append((bool(kept), section.get("title") or "Programmes",
                          f"{len(kept)} kept · {len(rows) - len(kept)} removed", []))
        elif kind == "table":
            rows = [r for r in (payload or []) if isinstance(r, dict)] if isinstance(payload, list) else []
            docs = [(x.get("name") or "file", links.file(stage_key, x))
                    for r in rows for v in r.values() for x in files_in(v)]
            items.append((bool(rows), section.get("title") or section["key"],
                          f"{len(rows)} row{'s' if len(rows) != 1 else ''}" if rows else "", docs))
    return items


def _documents(stage_key, data, links):
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("stored") and node.get("name"):
                out.append((node["name"], links.file(stage_key, node)))
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data or {})
    return out


def build(db, dept_code, year, links=None):
    links = links or NoLinks()
    dept = db.departments.find_one({"dept_code": dept_code}) or {}
    sub = db.submissions.find_one({"dept_code": dept_code, "academic_year": year}) or {}
    p = progress(sub)

    info = [("Department", dept.get("dept_name")), ("Department code", dept.get("dept_code")),
            ("Faculty", dept.get("faculty")), ("School", dept.get("school")),
            ("Campus", dept.get("campus")), ("Academic year", year),
            ("Progress", f"{p['done']} of {p['total']} stages submitted"),
            ("Report generated", datetime.now().strftime("%d %b %Y, %H:%M"))]

    stages = []
    for s in STAGES:
        if s.get("parts"):
            # Curriculum: one line here; its detail is under each programme
            codes = [x["programme_code"] for x in programmes_of(sub, dept)]
            states = [part_status(sub, c, k) for c in codes for k in PARTS]
            status = compute_status(sub, s["key"])
            if status != "locked" and states:
                status = ("submitted" if all(x == "submitted" for x in states) else
                          "returned" if "returned" in states else
                          "draft" if any(x in ("draft", "submitted") for x in states) else status)
            stages.append({"key": s["key"], "title": s["title"], "group": s["group"],
                           "status": status, "submitted_at": None,
                           "filled": states.count("submitted"), "total": len(states),
                           "unit": "programme parts submitted", "items": [],
                           "container": True, "returned_note": None})
            continue
        state = (sub.get("stages") or {}).get(s["key"]) or {}
        # never saved: what the stage opens with (the department's own record
        # and its catalogue programmes), so the report shows what is there
        data = state.get("data") or prefill_for(s["key"], dept, year, None, sub)
        items = section_items(s["key"], data, links)
        stages.append({
            "key": s["key"], "title": s["title"], "group": s["group"],
            "status": compute_status(sub, s["key"]),
            "submitted_at": state.get("submitted_at"),
            "filled": sum(1 for i in items if i[0]), "total": len(items),
            "items": items, "returned_note": state.get("returned_note"),
        })

    programmes = {"UG": [], "PG": []}
    for prog in programmes_of(sub, dept):
        code = prog["programme_code"]
        parts = []
        docs = []
        courses = 0
        for k in PARTS:
            state = (((sub.get("programmes") or {}).get(code) or {}).get(k)) or {}
            data = state.get("data") or {}
            if k == "prog_curriculum":
                courses = len(data.get("semester_structure") or [])
            parts.append({"key": k, "title": STAGE_BY_KEY[k]["title"],
                          "status": part_status(sub, code, k),
                          "errors": (state.get("summary") or {}).get("errors", 0)})
            docs += [(STAGE_BY_KEY[k]["title"], n, u) for n, u in _documents(k, data, links)]
        level = "PG" if prog.get("level") in ("PG", "PGD") else "UG"
        programmes[level].append({**prog, "parts": parts, "documents": docs, "courses": courses,
                                  "report": links.programme(code)})

    return {"dept": dept, "submission": sub, "year": year, "info": info,
            "stages": stages, "programmes": programmes}


def status_word(status):
    return STATUS_WORDS.get(status, (status or "").title())
