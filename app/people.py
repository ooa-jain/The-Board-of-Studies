"""Who is working, on a login a whole department shares — and every version
of what they saved, kept for five days so any of it can be brought back.

A department has one login, but two or three people may use it, sometimes
at the same time. Each says who they are (name and e-mail) once per
session; their saves are kept as versions under their name, and anyone on
the login can see who changed what and restore an earlier version.
"""

from __future__ import annotations

from datetime import timedelta

from .db import get_db, now

KEEP_DAYS = 5
FOLD_MINUTES = 15          # one person's saves on one stage, folded together
ACTIVE_MINUTES = 20        # “also working now”


def seen(dept_code, person):
    """The person is active on the department's login now."""
    if not person:
        return
    get_db().people.update_one(
        {"dept_code": dept_code, "email": person["email"].lower()},
        {"$set": {"name": person["name"], "last_seen": now()},
         "$setOnInsert": {"first_seen": now()}}, upsert=True)


def others_active(dept_code, person):
    """Everyone else on this login in the last few minutes."""
    since = now() - timedelta(minutes=ACTIVE_MINUTES)
    me = (person or {}).get("email", "").lower()
    return [p for p in get_db().people.find({"dept_code": dept_code, "last_seen": {"$gte": since}})
            .sort("last_seen", -1) if p.get("email") != me]


def known(dept_code):
    return list(get_db().people.find({"dept_code": dept_code}).sort("last_seen", -1).limit(12))


def keep(dept_code, year, stage_key, programme_code, data, person, kind="save"):
    """A version of a stage as saved. One person's saves within a quarter of
    an hour are one version; older than five days, versions are dropped."""
    db = get_db()
    t = now()
    db.versions.delete_many({"dept_code": dept_code, "at": {"$lt": t - timedelta(days=KEEP_DAYS)}})
    who = person or {"name": "Unknown", "email": ""}
    key = {"dept_code": dept_code, "academic_year": year, "stage": stage_key,
           "programme_code": programme_code or ""}
    if kind == "save":
        last = db.versions.find_one({**key, "kind": "save", "email": who.get("email", ""),
                                     "at": {"$gte": t - timedelta(minutes=FOLD_MINUTES)}},
                                    sort=[("at", -1)])
        newest = db.versions.find_one(key, sort=[("at", -1)])
        if last and newest and last["_id"] == newest["_id"]:
            db.versions.update_one({"_id": last["_id"]}, {"$set": {"data": data, "at": t},
                                                           "$inc": {"saves": 1}})
            return last["_id"]
    return db.versions.insert_one({**key, "data": data, "at": t, "first_at": t, "kind": kind,
                                   "name": who.get("name", ""), "email": who.get("email", ""),
                                   "saves": 1}).inserted_id


def history(dept_code, year, stage_key=None, programme_code=None):
    q = {"dept_code": dept_code, "academic_year": year,
         "at": {"$gte": now() - timedelta(days=KEEP_DAYS)}}
    if stage_key:
        q["stage"] = stage_key
        q["programme_code"] = programme_code or ""
    return list(get_db().versions.find(q).sort("at", -1).limit(300))
