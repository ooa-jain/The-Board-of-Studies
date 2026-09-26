"""Where each piece of a submission comes from, and where it is used again.

The portal asks for most things once and carries them forward. This module is
the list of those carries — the "data flows" — with, for one department (and
optionally one of its programmes), the actual value flowing along each one.
Admin > Flow 3D draws it; Admin > Flow 3D > Excel prints it.

A flow is one field (or one worked-out figure) moving from a source stage to
one or more target stages:

    how = "copied"      filled in as it is, read-only where it lands
          "worked out"  calculated from it (credits from L-T-P-E, averages …)
          "offered"     put forward to fill in one click ("Fill in all …")
"""

from __future__ import annotations

from .workflow import (programme_stage_state, programmes_of, stage_state)

# The places data lives, in the order a department meets them.
NODES = [
    {"key": "dept_info", "title": "Department Information", "group": "Level 0"},
    {"key": "pre_bos", "title": "Pre-BoS", "group": "Stage 1"},
    {"key": "bos_documents", "title": "BoS Documents", "group": "Stage 2"},
    {"key": "prog_curriculum", "title": "Curriculum", "group": "Stage 3"},
    {"key": "prog_syllabus", "title": "Syllabus", "group": "Stage 3"},
    {"key": "prog_revision", "title": "Course Revision", "group": "Stage 3"},
    {"key": "checks", "title": "Checks & summaries", "group": "Worked out"},
]

FLOWS = [
    {"id": "dept_name", "field": "Department name", "from": "dept_info",
     "to": ["prog_revision"], "how": "copied",
     "detail": "Department Information → Course Revision Log header"},
    {"id": "programmes", "field": "Programmes offered (code and name)", "from": "dept_info",
     "to": ["prog_curriculum", "prog_syllabus", "prog_revision"], "how": "copied",
     "detail": "Every programme kept here gets its own Curriculum, Syllabus and Course "
               "Revision, with its code and name filled in"},
    {"id": "degree", "field": "Degree / duration", "from": "prog_curriculum",
     "to": ["prog_revision", "checks"], "how": "copied",
     "detail": "Curriculum → Course Revision (UG / PG / PGD), duration in months and the "
               "UGC Table 2 column the credits are checked against"},
    {"id": "batch", "field": "Batch", "from": "prog_curriculum", "to": ["prog_syllabus"],
     "how": "copied", "detail": "Curriculum programme details → Syllabus header"},
    {"id": "specialisation", "field": "Specialisation", "from": "prog_curriculum",
     "to": ["prog_curriculum", "prog_revision"], "how": "copied",
     "detail": "Programme details → item 9 Course & specialisation, and the Course "
               "Revision Log header"},
    {"id": "bos_date", "field": "BoS meeting date", "from": "bos_documents",
     "to": ["prog_revision", "prog_syllabus"], "how": "copied",
     "detail": "BoS Documents → Course Revision Log BoS date, and the year of latest "
               "revision on every syllabus"},
    {"id": "courses", "field": "Courses (code, title, semester, credits)", "from": "prog_curriculum",
     "to": ["prog_syllabus"], "how": "offered",
     "detail": "Programme structure → Syllabus “Fill in all courses”"},
    {"id": "hours", "field": "Hours per week and teaching hours", "from": "prog_curriculum",
     "to": ["prog_syllabus"], "how": "worked out",
     "detail": "L + T + P + E hours per week, × 15 weeks for total teaching hours"},
    {"id": "credits", "field": "Credits", "from": "prog_curriculum", "to": ["checks"],
     "how": "worked out",
     "detail": "From L-T-P-E → Classification of Credits → Summary → UGC Table 2 check"},
    {"id": "marks", "field": "Total marks", "from": "prog_curriculum", "to": ["checks"],
     "how": "worked out", "detail": "Continuous assessment + term end → Summary total marks"},
    {"id": "syllabus_change", "field": "% change per module and per course", "from": "prog_syllabus",
     "to": ["checks", "prog_revision"], "how": "worked out",
     "detail": "Module % → course average → (A)–(D) summary, and the % change on the "
               "Course Revision Log"},
    {"id": "previous", "field": "Previous code, title and year", "from": "prog_syllabus",
     "to": ["prog_revision"], "how": "offered",
     "detail": "Syllabus revision table → Course Revision “Fill in all revisions”"},
    {"id": "revision_counts", "field": "Major / minor revision counts", "from": "prog_revision",
     "to": ["prog_revision"], "how": "worked out",
     "detail": "Counted from the revised courses into the log header"},
]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _n(k, one, many=None):
    return f"{k} {one if k == 1 else (many or one + 's')}"


def _fmt(n):
    return "" if n is None else (str(int(n)) if float(n).is_integer() else f"{n:.2f}")


def flows_for(submission: dict, department: dict, programme_code: str | None = None):
    """The flows, each with the value it carries for this department — and,
    when a programme is chosen, for that programme."""
    sub = submission or {}
    progs = programmes_of(sub, department) if sub else []
    prog = next((p for p in progs if p["programme_code"] == programme_code), None)
    ident = (stage_state(sub, "dept_info").get("data") or {}).get("identity") or {}
    meeting = (stage_state(sub, "bos_documents").get("data") or {}).get("meeting") or {}

    def pdata(key):
        if not prog:
            return {}
        return programme_stage_state(sub, prog["programme_code"], key).get("data") or {}

    cur, syl, rev = pdata("prog_curriculum"), pdata("prog_syllabus"), pdata("prog_revision")
    structure = [r for r in cur.get("semester_structure") or [] if isinstance(r, dict)]
    courses = [r for r in syl.get("courses") or [] if isinstance(r, dict)]
    revisions = [r for r in rev.get("revisions") or [] if isinstance(r, dict)]
    ug = sum(1 for p in progs if p.get("level") not in ("PG", "PGD"))

    credits = sum(_num(r.get("credits")) or 0 for r in structure)
    marks = sum(_num(r.get("total_marks")) or 0 for r in structure)
    hours = [sum(_num(r.get(k)) or 0 for k in "ltpe") for r in structure]
    avgs = [_num(c.get("avg_change")) for c in courses if _num(c.get("avg_change")) is not None]

    values = {
        "dept_name": ident.get("dept_name") or department.get("dept_name", ""),
        "programmes": (f"{len(progs)} programmes · {ug} UG, {len(progs) - ug} PG"
                       if progs else "No programmes kept yet"),
        "degree": (prog or {}).get("degree_level") or "",
        "batch": (prog or {}).get("batch") or "",
        "specialisation": (prog or {}).get("specialisation") or "",
        "bos_date": meeting.get("bos_date") or "",
        "courses": (f"{_n(len(structure), 'course')} in the structure · "
                    f"{_n(len(courses), 'syllabus', 'syllabi')}" if prog else ""),
        "hours": (f"{int(sum(hours))} hours a week across {_n(len(hours), 'course')}" if hours else ""),
        "credits": f"{_fmt(credits)} credits" if structure else "",
        "marks": f"{_fmt(marks)} marks" if structure else "",
        "syllabus_change": (f"Average {_fmt(sum(avgs) / len(avgs))}% across {_n(len(avgs), 'course')}"
                            if avgs else ""),
        "previous": (f"{_n(sum(1 for c in courses if c.get('prev_code') or c.get('prev_title')), 'course')} "
                     f"with a previous version" if courses else ""),
        "revision_counts": (
            f"{sum(1 for r in revisions if r.get('revision_type') == 'Major Revision')} major · "
            f"{sum(1 for r in revisions if r.get('revision_type') == 'Minor Revision')} minor"
            if revisions else ""),
    }
    per_programme = {"degree", "batch", "specialisation", "courses", "hours", "credits",
                     "marks", "syllabus_change", "previous", "revision_counts"}
    out = []
    for f in FLOWS:
        v = values.get(f["id"], "")
        if not v and f["id"] in per_programme and not prog:
            v = "Choose a programme to see its value"
        out.append({**f, "value": v or "Not filled yet"})
    return {
        "nodes": NODES,
        "flows": out,
        "department": {"code": department.get("dept_code"),
                       "name": values["dept_name"], "campus": department.get("campus", "")},
        "programmes": [{"code": p["programme_code"], "name": p["programme_name"],
                        "level": "PG" if p.get("level") in ("PG", "PGD") else "UG"}
                       for p in progs],
        "programme": ({"code": prog["programme_code"], "name": prog["programme_name"]}
                      if prog else None),
    }
