"""Uploaded files kept in Google Drive.

Typed answers live in MongoDB. The files departments upload (PDF, Word,
images) are copied into a Google Drive folder through a small Apps Script
web app (deploy/drive_script.gs) that runs as the Drive's owner — no Google
Cloud project needed.

    .env
    FILE_STORE=drive                 # "disk" (the default) keeps files on the server only
    DRIVE_SCRIPT_URL=https://script.google.com/macros/s/…/exec
    DRIVE_SCRIPT_SECRET=…            # the SECRET script property, word for word

How it works: every upload is still written to the server first (the keyword
check and the preview read it there), then sent to Drive in the background;
its record in MongoDB keeps the Drive file id. When the server copy is gone
(pruned with tools/drive_sync.py, or a new server), the file is fetched back
from Drive the first time it is opened. Drive is the lasting copy; the
server's uploads folder is a cache.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import threading
import urllib.request
from pathlib import Path

from flask import current_app

from .db import get_db, now


class DriveError(Exception):
    pass


def _cfg(app=None):
    c = (app or current_app).config
    return (c.get("FILE_STORE") or "disk").lower(), c.get("DRIVE_SCRIPT_URL") or "", c.get("DRIVE_SCRIPT_SECRET") or ""


def configured(app=None) -> bool:
    """Can the portal reach the Drive at all (to send, or to fetch back)?"""
    _, url, secret = _cfg(app)
    return bool(url and secret)


def enabled(app=None) -> bool:
    """Are new uploads sent to Drive?"""
    mode, _, _ = _cfg(app)
    return mode == "drive" and configured(app)


def _call(payload: dict, timeout=120, app=None) -> dict:
    _, url, secret = _cfg(app)
    if not (url and secret):
        raise DriveError("DRIVE_SCRIPT_URL and DRIVE_SCRIPT_SECRET are not set in .env.")
    body = json.dumps({**payload, "secret": secret}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    # Apps Script answers a POST with a redirect to the result, which urllib
    # follows as a GET — exactly what the script expects
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as e:
        raise DriveError(f"Drive could not be reached: {e}") from None
    try:
        out = json.loads(raw)
    except ValueError:
        raise DriveError("Drive answered with something other than the script's reply — "
                         "check DRIVE_SCRIPT_URL and that the script is deployed for Anyone.") from None
    if not out.get("ok"):
        raise DriveError(f"Drive refused: {out.get('error') or 'no reason given'}")
    return out


def ping(app=None) -> dict:
    """{"ok": True, "root": folder id} when the script and the secret are right."""
    return _call({"action": "ping"}, timeout=60, app=app)


def local_path(rec: dict, app=None) -> Path:
    """Where a file record lives on the server (whether or not it is there now)."""
    root = (app or current_app).config["UPLOAD_ROOT"]
    return Path(root) / (rec.get("academic_year") or "") / rec["dept_code"] / rec["stage"] / rec["stored_name"]


def put(rec: dict, app=None) -> str:
    """Send one file to Drive, into Year / Department / Stage; returns its Drive id."""
    path = local_path(rec, app)
    data = path.read_bytes()
    mime = mimetypes.guess_type(rec.get("original_name") or path.name)[0] or "application/octet-stream"
    folder = "/".join([rec.get("academic_year") or "", rec["dept_code"], rec["stage"]])
    out = _call({"action": "put", "path": folder, "name": rec["stored_name"], "mime": mime,
                 "data": base64.b64encode(data).decode()}, app=app)
    return out["id"]


def push(rec: dict, app=None) -> str | None:
    """Send a file to Drive and note its id on the record; a failure is noted
    too, and tools/drive_sync.py sends it again later."""
    db = get_db()
    try:
        fid = put(rec, app)
    except Exception as e:
        db.files.update_one({"_id": rec["_id"]}, {"$set": {"drive_error": str(e)[:300]}})
        (app or current_app).logger.warning("Drive upload failed for %s: %s", rec.get("stored_name"), e)
        return None
    db.files.update_one({"_id": rec["_id"]}, {"$set": {"drive_id": fid, "drive_at": now()},
                                              "$unset": {"drive_error": ""}})
    return fid


def push_later(rec_id) -> None:
    """After an upload: send it to Drive without keeping the department waiting."""
    if not enabled():
        return
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            rec = get_db().files.find_one({"_id": rec_id})
            if rec and not rec.get("drive_id"):
                push(rec, app)

    threading.Thread(target=run, daemon=True).start()


def ensure_local(rec: dict, app=None) -> Path:
    """The file on the server, fetched back from Drive first if it is not there."""
    path = local_path(rec, app)
    if path.exists() or not rec.get("drive_id") or not configured(app):
        return path
    try:
        out = _call({"action": "get", "id": rec["drive_id"]}, app=app)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(base64.b64decode(out["data"]))
        tmp.replace(path)
    except Exception as e:
        (app or current_app).logger.warning("Could not fetch %s from Drive: %s", rec.get("stored_name"), e)
    return path


def trash_later(drive_ids) -> None:
    """Move files to the Drive's bin (kept 30 days there) — after a department is deleted."""
    ids = [i for i in drive_ids if i]
    if not ids or not configured():
        return
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            for fid in ids:
                try:
                    _call({"action": "trash", "id": fid}, timeout=60, app=app)
                except Exception as e:
                    app.logger.warning("Could not move %s to the Drive bin: %s", fid, e)

    threading.Thread(target=run, daemon=True).start()
