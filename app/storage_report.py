"""Admin > Settings > Storage: where the portal keeps what, and how much.

Typed answers are in MongoDB; uploaded files in Google Drive (through the
Apps Script, app/drive_store.py), with a working copy on the server. The
figures come from MongoDB's own statistics, the file records, and the
server's disk; the Drive is asked once every ten minutes at most.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from flask import current_app

from . import drive_store
from .db import get_db

# what each collection holds, in words
COLLECTIONS = {
    "submissions": "Every stage and programme a department has filled",
    "versions": "Saved versions — each submit, for Version History",
    "files": "One record per uploaded file (the file itself is in Drive)",
    "audit": "Audit log — sign-ins, submissions, changes",
    "notifications": "Updates shown to the Office and departments",
    "comments": "Comments on submissions",
    "departments": "Departments and their details",
    "users": "Logins — departments and the Office team",
    "people": "Who filled in, per department",
    "settings": "Portal settings",
    "rules": "Credit rules (UGC tables)",
    "connectors": "Connectors — where updates are sent",
}

TYPES = [("PDF", {".pdf"}), ("Word", {".doc", ".docx"}), ("Excel", {".xls", ".xlsx", ".csv"}),
         ("PowerPoint", {".ppt", ".pptx"}), ("Images", {".png", ".jpg", ".jpeg", ".webp", ".gif"}),
         ("Zip", {".zip"})]

_drive_cache: dict = {}


def size(n) -> str:
    """Bytes in words: 812 KB, 38.4 MB, 1.25 GB."""
    if n is None:
        return "—"
    n = float(n)
    for unit, step in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= step:
            v = n / step
            return f"{v:.2f} {unit}" if unit == "GB" else f"{v:.1f} {unit}"
    return f"{int(n)} bytes"


def _host(uri: str) -> str:
    """The cluster's address, without the login in front of it."""
    rest = (uri or "").split("//", 1)[-1]
    return rest.split("@", 1)[-1].split("/", 1)[0].split("?", 1)[0]


def _coll_size(db, name):
    """(data bytes, on-disk bytes, index bytes) for one collection."""
    try:
        s = db.command("collStats", name)
        return s.get("size"), s.get("storageSize"), s.get("totalIndexSize")
    except Exception:
        pass
    try:      # the documents' own size, added up by the database
        r = list(db[name].aggregate([{"$group": {"_id": None, "b": {"$sum": {"$bsonSize": "$$ROOT"}}}}]))
        return (r[0]["b"] if r else 0), None, None
    except Exception:
        pass
    try:      # last resort (a test database): measured here
        import bson
        return sum(len(bson.encode(d)) for d in db[name].find()), None, None
    except Exception:
        return None, None, None


def mongo() -> dict:
    db = get_db()
    rows = []
    for name in sorted(db.list_collection_names()):
        if name.startswith("system."):
            continue
        data, disk, idx = _coll_size(db, name)
        rows.append({"name": name, "about": COLLECTIONS.get(name, ""),
                     "records": db[name].estimated_document_count(),
                     "data": data, "disk": disk, "index": idx})
    rows.sort(key=lambda r: -(r["data"] or 0))
    out = {"db": db.name, "host": _host(current_app.config.get("MONGO_URI", "")), "collections": rows,
           "records": sum(r["records"] for r in rows), "data": sum(r["data"] or 0 for r in rows),
           "disk": None, "index": None}
    try:
        s = db.command("dbStats")
        out.update(data=s.get("dataSize", out["data"]), disk=s.get("storageSize"), index=s.get("indexSize"))
    except Exception:
        pass
    return out


def _kind(name: str) -> str:
    ext = Path(name or "").suffix.lower()
    return next((k for k, exts in TYPES if ext in exts), "Other")


def drive(refresh=False) -> dict:
    db = get_db()
    depts = {d["dept_code"]: d.get("dept_name") or d["dept_code"]
             for d in db.departments.find({}, {"dept_code": 1, "dept_name": 1})}
    files = list(db.files.find({}, {"original_name": 1, "size": 1, "drive_id": 1, "drive_error": 1,
                                    "dept_code": 1}))
    inside = [f for f in files if f.get("drive_id")]
    waiting = [f for f in files if not f.get("drive_id")]
    kinds, by_dept = {}, {}
    for f in inside:
        k = kinds.setdefault(_kind(f.get("original_name")), {"files": 0, "bytes": 0})
        k["files"] += 1
        k["bytes"] += f.get("size") or 0
        d = by_dept.setdefault(f.get("dept_code"), {"files": 0, "bytes": 0})
        d["files"] += 1
        d["bytes"] += f.get("size") or 0
    out = {
        "on": drive_store.enabled(), "configured": drive_store.configured(),
        "files": len(inside), "bytes": sum(f.get("size") or 0 for f in inside),
        "waiting": len(waiting), "waiting_bytes": sum(f.get("size") or 0 for f in waiting),
        "errors": sum(1 for f in waiting if f.get("drive_error")),
        "kinds": sorted(({"kind": k, **v} for k, v in kinds.items()), key=lambda r: -r["bytes"]),
        "departments": sorted(({"code": c, "name": depts.get(c, c), **v} for c, v in by_dept.items()),
                              key=lambda r: -r["bytes"]),
        "folder": None, "account_used": None, "account_limit": None, "reach_error": None, "asked_at": None,
    }
    if out["configured"]:
        hit = _drive_cache.get("ping")
        if refresh or not hit or time.time() - hit[0] > 600:
            try:
                hit = (time.time(), drive_store.ping(), None)
            except Exception as e:
                hit = (time.time(), {}, str(e))
            _drive_cache["ping"] = hit
        at, ping, error = hit
        out["asked_at"] = at
        out["reach_error"] = error
        if ping.get("root"):
            out["folder"] = f"https://drive.google.com/drive/folders/{ping['root']}"
        # an updated script also reports the Drive account's own storage
        out["account_used"] = ping.get("used")
        lim = ping.get("limit")
        out["account_limit"] = lim if isinstance(lim, (int, float)) and lim > 0 else None
    return out


def server() -> dict:
    root = Path(current_app.config["UPLOAD_ROOT"])
    n = total = thumbs = 0
    for dirpath, _, names in os.walk(root):
        for name in names:
            try:
                b = (Path(dirpath) / name).stat().st_size
            except OSError:
                continue
            if name.endswith(".thumb.png"):
                thumbs += b
            else:
                n += 1
                total += b
    try:
        du = shutil.disk_usage(root)
        disk = {"total": du.total, "used": du.used, "free": du.free}
    except OSError:
        disk = None
    return {"files": n, "bytes": total, "thumbs": thumbs, "disk": disk}


def report(refresh=False) -> dict:
    return {"mongo": mongo(), "drive": drive(refresh), "server": server()}
