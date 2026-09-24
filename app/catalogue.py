"""The Office of Academics programme catalogue, and which rows belong to whom.

app/data/programmes.json is built from the programme workbook by
tools/import_programmes.py. The workbook names a department and a Bengaluru
campus, plus a Yes in a Kochi column for programmes also run at Kochi. The
department master spells both a little differently ("&" for "and",
"Sheshadri" for "Seshadhri", "Jain Global Campus" for "... - Kanakapura"), so
matching is done on normalised names and on the campus's place name.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parent / "data" / "programmes.json"

# Place names that tell campuses apart, with the spellings each goes by.
_PLACES = {
    "sports school": ("sports school",),
    "global": ("jain global", "kanakapura"),
    "jayanagar": ("jayanagar",),
    "jc road": ("jc road",),
    "lalbagh": ("lalbagh",),
    "whitefield": ("whitefield",),
    "yelahanka": ("yelahanka",),
    "jp nagar": ("jp nagar",),
    "sheshadri": ("sheshadri", "seshadhri", "seshadri"),
    "shankar mutt": ("shankar mutt",),
    "kochi": ("kochi",),
}


@lru_cache(maxsize=1)
def load() -> tuple:
    try:
        return tuple(json.loads(CATALOGUE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return ()


def _name(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"^department of\s+", "", s.strip())
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())


def _places(s: str) -> set[str]:
    s = (s or "").lower()
    # "The Sports School - Kanakapura Road" is not the Global Campus
    if "sports school" in s:
        return {"sports school"}
    return {key for key, spellings in _PLACES.items() if any(x in s for x in spellings)}


def programmes_for(department: dict, departments: list[dict] | None = None) -> list[dict]:
    """Catalogue rows for one department record, in workbook order.

    `departments` is the whole master. It is only needed when the workbook's
    campus does not line up with any record's campus: a department that has
    a single Bengaluru record then takes every Bengaluru row of its name.
    """
    name = _name(department.get("dept_name"))
    if not name:
        return []
    rows = [r for r in load() if _name(r["department"]) == name]
    places = _places(department.get("campus"))

    if "kochi" in places:
        return [r for r in rows if r.get("kochi")]

    mine = [r for r in rows if places & _places(r.get("location"))]
    if mine or departments is None:
        return mine

    siblings = [d for d in departments
                if _name(d.get("dept_name")) == name
                and "kochi" not in _places(d.get("campus"))]
    return rows if len(siblings) == 1 else []
