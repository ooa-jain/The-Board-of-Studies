"""Queries from departments — the Query button on the right of every
department page.

Technical: how to use the portal. The department is shown the sections of
the Help walkthrough and goes straight to the one it needs; nothing is
stored. Academics: a question for the Office of Academic Affairs. It is
raised as a ticket (Q-0001, Q-0002…), listed on the admin Queries page and
put on the Updates feed.

Email: the department is to get a mail when its ticket is raised and when it
is resolved. The Office will give the mail details later, so send_mail() is a
placeholder for now — tickets work without it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pymongo import ReturnDocument

from .db import get_db, now

MAX_TEXT = 3000
MAX_SUBJECT = 150


def help_sections(static_folder) -> list[dict]:
    """The sections of the Help walkthrough (static/help/chapters.json)."""
    try:
        chapters = json.loads((Path(static_folder) / "help" / "chapters.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"n": i + 1, "title": c.get("title", ""), "sub": c.get("sub", "")}
            for i, c in enumerate(chapters) if isinstance(c, dict)]


def _next_number() -> int:
    doc = get_db().counters.find_one_and_update(
        {"_id": "queries"}, {"$inc": {"n": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return int(doc["n"])


def ticket_no(n) -> str:
    return f"Q-{int(n):04d}"


def raise_ticket(dept: dict, *, subject: str, text: str, person: dict | None,
                 page: str = "", year: str = "", actor: str = "") -> dict:
    """Store an Academics query as a ticket and return it."""
    n = _next_number()
    doc = {
        "number": n, "ticket": ticket_no(n), "kind": "academics",
        "dept_code": dept["dept_code"], "dept_name": dept.get("dept_name", ""),
        "campus": dept.get("campus", ""), "academic_year": year,
        "subject": subject[:MAX_SUBJECT], "text": text[:MAX_TEXT],
        "name": (person or {}).get("name", ""), "email": (person or {}).get("email", ""),
        "actor": actor, "page": page[:300], "status": "open", "at": now(),
    }
    doc["_id"] = get_db().queries.insert_one(doc).inserted_id
    send_mail(doc, "raised")
    return doc


def set_status(ticket_id, status: str, by: str, extra_q: dict | None = None) -> bool:
    if status not in ("open", "resolved"):
        raise ValueError(status)
    change = {"status": status}
    if status == "resolved":
        change.update(resolved_at=now(), resolved_by=by)
    res = get_db().queries.update_one({"_id": ticket_id, **(extra_q or {})},
                                      {"$set": change} if status == "resolved"
                                      else {"$set": change, "$unset": {"resolved_at": "", "resolved_by": ""}})
    if res.modified_count and status == "resolved":
        doc = get_db().queries.find_one({"_id": ticket_id})
        if doc:
            send_mail(doc, "resolved")
    return bool(res.modified_count)


def send_mail(ticket: dict, what: str) -> None:
    """On hold: the Office will give the mail details later. Until then
    nothing is sent; the ticket is on the Queries page and in Updates."""
    return None


def open_count(extra_q: dict | None = None) -> int:
    return get_db().queries.count_documents({"status": "open", **(extra_q or {})})
