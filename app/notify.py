"""Updates for the Office: whenever a department changes anything, a record
of what changed — field by field — and a message to every connector the
admin has set up (email, Slack, Microsoft Teams, Google Chat, Discord, or any
webhook).

A department typing into a form saves every few seconds, so saves are folded
together: the same department, stage and programme within half an hour adds
to the one update rather than writing a new one each time.
"""

from __future__ import annotations

import json
import smtplib
import threading
import urllib.error
import urllib.request
from datetime import timedelta
from email.message import EmailMessage

from bson import ObjectId
from flask import current_app

from .db import get_db, now
from .schema import STAGE_BY_KEY

FOLD_MINUTES = 30
MAX_CHANGES = 40

# what can happen, how it reads, and whether connectors hear about it unless
# the admin says otherwise
EVENTS = {
    "submitted": ("Stage submitted", True),
    "saved": ("Data changed", False),
    "uploaded": ("File uploaded", True),
    "keyword_miss": ("Upload failed the keyword check", True),
    "programme": ("Programmes changed", True),
    "password": ("Password changed", False),
}

KINDS = {
    "email": "Email",
    "slack": "Slack",
    "teams": "Microsoft Teams",
    "google_chat": "Google Chat",
    "discord": "Discord",
    "webhook": "Webhook (JSON)",
}


# ---------------------------------------------------------------------------
# what changed
# ---------------------------------------------------------------------------

def _short(v, n=80):
    if v is None or v == "":
        return "—"
    if isinstance(v, dict) and v.get("name"):          # an uploaded file
        return "file: " + str(v["name"])
    if isinstance(v, list):
        if v and all(isinstance(x, dict) and x.get("name") for x in v):
            return ", ".join(str(x["name"]) for x in v)[:n]
        return f"{len(v)} item{'s' if len(v) != 1 else ''}"
    if isinstance(v, dict):
        return f"{len(v)} values"
    s = " ".join(str(v).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _labels(stage_key):
    stage = STAGE_BY_KEY.get(stage_key) or {}
    out = {}
    for sec in stage.get("sections", []):
        cols = {c["name"]: c.get("label") or c["name"] for c in sec.get("columns", [])}
        fields = {f["name"]: f.get("label") or f["name"] for f in sec.get("fields", [])}
        out[sec["key"]] = (sec.get("title") or sec["key"], {**cols, **fields})
    return out


def describe_changes(stage_key, old, new):
    """[{section, field, before, after}] — what a save changed, in the words
    the form uses."""
    old, new = old or {}, new or {}
    labels = _labels(stage_key)
    changes = []
    for key in list(dict.fromkeys(list(new) + list(old))):
        a, b = old.get(key), new.get(key)
        if a == b:
            continue
        title, names = labels.get(key, (key.replace("_", " ").capitalize(), {}))
        if isinstance(a, dict) or isinstance(b, dict):
            a, b = a if isinstance(a, dict) else {}, b if isinstance(b, dict) else {}
            for f in list(dict.fromkeys(list(b) + list(a))):
                if a.get(f) != b.get(f) and not (a.get(f) in (None, "") and b.get(f) in (None, "")):
                    changes.append({"section": title, "field": names.get(f, f),
                                    "before": _short(a.get(f)), "after": _short(b.get(f))})
        elif isinstance(a, list) or isinstance(b, list):
            a, b = a if isinstance(a, list) else [], b if isinstance(b, list) else []
            if len(a) != len(b):
                changes.append({"section": title, "field": "Rows",
                                "before": str(len(a)), "after": str(len(b))})
            for i, (ra, rb) in enumerate(zip(a, b)):
                if ra == rb or not isinstance(rb, dict):
                    continue
                ra = ra if isinstance(ra, dict) else {}
                for f in rb:
                    if ra.get(f) != rb.get(f) and not (ra.get(f) in (None, "") and rb.get(f) in (None, "")):
                        changes.append({"section": title, "field": f"Row {i + 1} · {names.get(f, f)}",
                                        "before": _short(ra.get(f)), "after": _short(rb.get(f))})
        else:
            changes.append({"section": title, "field": names.get(key, key),
                            "before": _short(a), "after": _short(b)})
        if len(changes) >= MAX_CHANGES:
            break
    return changes[:MAX_CHANGES]


def _merge(earlier, later):
    """Fold a later save's changes into an update: one line per field, the
    first 'before' and the latest 'after'."""
    seen = {(c["section"], c["field"]): dict(c) for c in earlier}
    for c in later:
        k = (c["section"], c["field"])
        if k in seen:
            seen[k]["after"] = c["after"]
        else:
            seen[k] = dict(c)
    out = [c for c in seen.values() if c["before"] != c["after"]]
    return out[:MAX_CHANGES]


# ---------------------------------------------------------------------------
# recording
# ---------------------------------------------------------------------------

def stage_title(stage_key):
    return (STAGE_BY_KEY.get(stage_key) or {}).get("title", stage_key or "")


def record(dept, event, *, stage_key=None, programme=None, changes=None, text="", actor="", person=""):
    """Write one update (or add to the open one) and tell the connectors."""
    if event not in EVENTS:
        raise ValueError(event)
    db = get_db()
    prog_code = (programme or {}).get("programme_code")
    at = now()
    base = {"dept_code": dept["dept_code"], "dept_name": dept.get("dept_name", ""),
            "campus": dept.get("campus", ""), "event": event, "stage": stage_key or "",
            "stage_title": stage_title(stage_key) if stage_key else "",
            "programme_code": prog_code or "",
            "programme_name": (programme or {}).get("programme_name", ""),
            "person": person or ""}

    if event == "saved":
        if not changes:
            return None
        open_one = db.notifications.find_one({
            "dept_code": base["dept_code"], "event": "saved", "stage": base["stage"],
            "programme_code": base["programme_code"], "read": False, "person": base["person"],
            "at": {"$gte": at - timedelta(minutes=FOLD_MINUTES)}})
        if open_one:
            merged = _merge(open_one.get("changes", []), changes)
            db.notifications.update_one({"_id": open_one["_id"]}, {
                "$set": {"changes": merged, "at": at, "text": _text(event, base, merged, text)},
                "$inc": {"saves": 1}})
            return open_one["_id"]

    doc = {**base, "changes": changes or [], "text": _text(event, base, changes or [], text),
           "actor": actor, "at": at, "first_at": at, "read": False, "saves": 1}
    _id = db.notifications.insert_one(doc).inserted_id
    doc["_id"] = _id
    dispatch(doc)
    return _id


def _text(event, base, changes, extra):
    where = base["stage_title"]
    if base["programme_name"]:
        where = f"{base['programme_name']} · {where}"
    words = EVENTS[event][0]
    line = f"{base['dept_name']} — {words}" + (f": {where}" if where else "")
    if extra:
        line += f". {extra}"
    elif changes:
        line += f" ({len(changes)} field{'s' if len(changes) != 1 else ''})"
    return line


def unread_count():
    return get_db().notifications.count_documents({"read": False})


# ---------------------------------------------------------------------------
# connectors
# ---------------------------------------------------------------------------

def _link(note):
    base = current_app.config.get("PUBLIC_URL") or ""
    return f"{base}/admin/submissions/{note['dept_code']}" if base else ""


def message(note):
    lines = [note["text"]]
    for c in (note.get("changes") or [])[:8]:
        lines.append(f"• {c['section']} › {c['field']}: {c['before']} → {c['after']}")
    more = len(note.get("changes") or []) - 8
    if more > 0:
        lines.append(f"…and {more} more")
    link = _link(note)
    if link:
        lines.append(link)
    return "\n".join(lines)


def _post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def _payload(kind, note):
    text = message(note)
    if kind == "slack":
        return {"text": text}
    if kind == "discord":
        return {"content": text[:1990]}
    if kind == "google_chat":
        return {"text": text}
    if kind == "teams":
        return {"text": text.replace("\n", "<br>")}
    return {"event": note["event"], "text": note["text"], "department": note["dept_name"],
            "dept_code": note["dept_code"], "stage": note.get("stage"),
            "programme_code": note.get("programme_code"), "changes": note.get("changes", []),
            "at": note["at"].isoformat() if hasattr(note.get("at"), "isoformat") else str(note.get("at")),
            "link": _link(note)}


def smtp_ready():
    c = current_app.config
    return bool(c.get("SMTP_HOST") and c.get("SMTP_FROM"))


def _send_email(to, note):
    c = current_app.config
    if not smtp_ready():
        raise RuntimeError("Email is not set up on the server — add SMTP_HOST and SMTP_FROM to .env.")
    msg = EmailMessage()
    msg["Subject"] = "BoS Portal: " + note["text"][:150]
    msg["From"] = c["SMTP_FROM"]
    msg["To"] = ", ".join(to)
    msg.set_content(message(note) + "\n\n— BoS Academic Portal, Office of Academics")
    cls = smtplib.SMTP_SSL if c.get("SMTP_SSL") else smtplib.SMTP
    with cls(c["SMTP_HOST"], c["SMTP_PORT"], timeout=20) as s:
        if not c.get("SMTP_SSL"):
            s.starttls()
        if c.get("SMTP_USER"):
            s.login(c["SMTP_USER"], c["SMTP_PASSWORD"])
        s.send_message(msg)


def send_one(conn, note):
    """Send to one connector; returns (ok, words)."""
    try:
        if conn["kind"] == "email":
            to = [e.strip() for e in conn.get("target", "").replace(";", ",").split(",") if e.strip()]
            _send_email(to, note)
        else:
            _post_json(conn["target"], _payload(conn["kind"], note))
        return True, "Sent"
    except urllib.error.HTTPError as e:
        return False, f"Refused ({e.code})"
    except Exception as e:                     # network, SMTP, bad address
        return False, str(e)[:160] or e.__class__.__name__


def wants(conn, note):
    if not conn.get("active"):
        return False
    events = conn.get("events")
    if events is None:
        events = [k for k, (_, on) in EVENTS.items() if on]
    if note["event"] not in events:
        return False
    only = (conn.get("departments") or "").strip()
    if only:
        codes = {c.strip().upper() for c in only.replace(";", ",").split(",") if c.strip()}
        return note["dept_code"].upper() in codes
    return True


def _deliver(app, note, conns):
    with app.app_context():
        db = get_db()
        for conn in conns:
            ok, words = send_one(conn, note)
            db.connectors.update_one({"_id": conn["_id"]}, {
                "$set": {"last_at": now(), "last_ok": ok, "last_status": words},
                "$inc": {"sent" if ok else "failed": 1}})


def dispatch(note):
    conns = [c for c in get_db().connectors.find({"active": True}) if wants(c, note)]
    if not conns:
        return
    app = current_app._get_current_object()
    if app.config.get("CONNECTORS_SYNC") or app.config.get("TESTING"):
        _deliver(app, note, conns)
    else:
        threading.Thread(target=_deliver, args=(app, note, conns), daemon=True).start()


def test_note(dept_name="Department of Demonstration"):
    return {"_id": ObjectId(), "dept_code": "TEST", "dept_name": dept_name, "event": "submitted",
            "stage": "dept_info", "programme_code": "", "at": now(),
            "text": f"Test message from the BoS Academic Portal — {dept_name}",
            "changes": [{"section": "Department", "field": "Vision", "before": "—", "after": "A test value"}]}
