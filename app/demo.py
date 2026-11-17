"""
Invented data for the analysis screen.

There is nothing real in this file. It exists so the Office can show the
analysis to people before departments have filed anything, and it is written
to be thrown away: the whole feature is this module, one `if` in
`admin.analysis`, and one tab in the template. Delete those three and nothing
else changes.

Every row it makes is marked `demo: True`, the screen says so in a banner it
cannot be shown without, and the numbers are drawn from a fixed seed so the
same demonstration shows the same figures twice running.
"""

from __future__ import annotations

import random
from datetime import timedelta

from .db import now
from .schema import STAGES
from .workflow import institution_analysis, stage_analysis

SEED = 20260921

# A department, its school and campus — enough to look like the real master
# without being any actual department's record.
_SAMPLE = [
    ("Department of Computer Science and Engineering",
     "School of Computer Science and Engineering", "Jain Global Campus", "Bangalore"),
    ("Department of Information Science and Engineering",
     "School of Computer Science and Engineering", "Jain Global Campus", "Bangalore"),
    ("Department of Aerospace Engineering",
     "School of Aerospace Engineering", "Jain Global Campus", "Bangalore"),
    ("Department of Civil Engineering",
     "School of Engineering & Technology", "Jain Global Campus", "Bangalore"),
    ("Department of Mechanical Engineering",
     "School of Engineering & Technology", "Jain Global Campus", "Bangalore"),
    ("Department of Commerce", "School of Commerce", "Jayanagar Campus", "Bangalore"),
    ("Department of Commerce", "School of Commerce", "Kochi Campus", "Kochi"),
    ("Department of Management Studies", "CMS Business School",
     "Sheshadri Road Campus", "Bangalore"),
    ("Department of Economics", "School of Humanities and Social Sciences",
     "Jayanagar Campus", "Bangalore"),
    ("Department of Law", "School of Law", "Sheshadri Road Campus", "Bangalore"),
    ("Department of Chemistry and Biochemistry", "School of Sciences",
     "JC Road Campus", "Bangalore"),
    ("Department of Biotechnology and Genetics", "School of Sciences",
     "JC Road Campus", "Bangalore"),
    ("Department of Forensic Science", "School of Sciences", "Kochi Campus", "Kochi"),
    ("Department of Psychology and Allied Sciences", "School of Sciences",
     "JC Road Campus", "Bangalore"),
    ("Department of Design", "School of Design, Media and Creative Arts",
     "Yelahanka Campus", "Bangalore"),
    ("Department of Journalism and Mass Communication",
     "School of Humanities and Social Sciences", "Lalbagh Campus", "Bangalore"),
    ("Department of Computer Science and IT",
     "School of Computer Science & Information Technology", "Jayanagar Campus", "Bangalore"),
    ("Department of Allied Healthcare and Sciences",
     "School of Allied Healthcare and Sciences", "Whitefield Campus", "Bangalore"),
]

# How the invented departments are spread. Roughly what a cycle a few weeks in
# looks like: a few finished, most part-way, a tail that has not started.
_SHAPE = [
    "complete", "complete", "complete",
    "returned",
    "in_progress", "in_progress", "in_progress", "in_progress",
    "in_progress", "in_progress", "in_progress",
    "not_started", "not_started",
    "never_in", "never_in", "never_in",
    "no_login", "no_login",
]

_LABEL = {
    "complete": "All stages submitted",
    "returned": "Sent back for correction",
    "in_progress": "In progress",
    "not_started": "Signed in, nothing filed",
    "never_in": "Never signed in",
    "no_login": "No login issued",
}


def _code(name, campus):
    stop = {"of", "and", "the", "for", "in", "department"}
    words = [w for w in name.replace("&", " ").split() if w.lower() not in stop]
    head = "".join(w[0] for w in words)[:4].upper() or "DEPT"
    tail = "".join(w[0] for w in campus.split())[:3].upper()
    return f"{head}-{tail}"


def _row(rng, name, school, campus, place, shape, total):
    """One invented department, shaped to look like a real one."""
    if shape == "complete":
        done, half, returned = total, 0, 0
    elif shape == "returned":
        done, half, returned = rng.randint(4, 9), rng.randint(0, 1), 1
    elif shape == "in_progress":
        done = rng.randint(1, total - 3)
        half, returned = rng.randint(0, 1), 0
    else:
        done, half, returned = 0, 0, 0

    errors = rng.choice([0, 0, 0, 1, 2, 3, 5]) if shape in ("in_progress", "returned") else 0
    warnings = rng.choice([0, 0, 1, 2, 4]) if done else 0
    signed_in = shape not in ("never_in", "no_login")

    last_login = None
    if signed_in:
        last_login = now() - timedelta(days=rng.randint(0, 21),
                                       hours=rng.randint(0, 23))
    updated = last_login - timedelta(hours=rng.randint(0, 40)) if (last_login and done) else None

    nxt = None
    if shape in ("in_progress", "returned", "not_started"):
        i = min(done, total - 1)
        nxt = {"key": STAGES[i]["key"], "title": STAGES[i]["title"],
               "status": "returned" if returned else ("draft" if half else "open")}

    return {
        "demo": True,
        "dept": {"dept_name": name, "school": school, "campus": campus, "place": place,
                 "dept_code": _code(name, campus),
                 "username": None if shape == "no_login" else "demo.login"},
        "state": shape,
        "label": _LABEL[shape],
        "done": done, "total": total,
        "percent": round(done * 100 / total) if total else 0,
        "half": half, "returned": returned,
        "locked": max(0, total - done - half - returned),
        "open": 1 if shape in ("in_progress", "not_started") else 0,
        "errors": errors, "warnings": warnings,
        "next": nxt,
        "has_login": shape != "no_login",
        "signed_in": signed_in,
        "last_login": last_login,
        "updated_at": updated,
        "sealed": shape == "complete" and rng.random() < 0.5,
    }


def demo_analysis():
    """The whole analysis screen's worth of invented data."""
    rng = random.Random(SEED)
    total = len(STAGES)

    rows = [_row(rng, name, school, campus, place, shape, total)
            for (name, school, campus, place), shape in zip(_SAMPLE, _SHAPE)]

    # stage_analysis reads boards, so give it one per department shaped to the
    # row: submitted up to `done`, then a draft, then locked
    boards = []
    for r in rows:
        board = []
        for i in range(total):
            if i < r["done"]:
                st = "submitted"
            elif i == r["done"] and r["returned"]:
                st = "returned"
            elif i == r["done"] and r["half"]:
                st = "draft"
            elif i == r["done"] and r["has_login"] and r["signed_in"]:
                st = "open"
            else:
                st = "locked"
            board.append({"status": st})
        boards.append(board)

    totals = institution_analysis(rows)
    return rows, totals, stage_analysis(boards)
