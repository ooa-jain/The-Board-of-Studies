"""Who in the Office may do what, and for which departments.

The first admin is a Full admin and may do everything. Team members the
Office adds get, for each section of the menu, None, View or Edit, a
separate Delete for what cannot be undone, and the departments they may
see: all of them, or a chosen set (by name, or a whole school or campus,
which takes in departments added to it later).

Every admin page and action names its section and what it needs (the
ENDPOINTS table below); anything not listed is for Full admins only, so a
new page is closed until it is placed.
"""

from __future__ import annotations

from flask import abort, g, request, session

# the menu's sections, in its order: key, label, what is in it
SECTIONS = [
    ("home", "Home", "The dashboard and the one-click analysis"),
    ("departments", "Departments", "Department master, logins and imports"),
    ("overview", "Overview", "Monitor, analysis, programmes, each department's record and its Excel / Word"),
    ("documents", "Documents", "Uploaded documents and their summaries"),
    ("comments", "Comments", "Comments to departments"),
    ("calendar", "Calendar", "What happened, day by day"),
    ("flow", "Flow 3D", "How a department's data flows"),
    ("updates", "Updates", "Changes from departments as they happen"),
    ("settings", "Settings", "Portal settings, credit rules, keywords, connectors, audit log"),
]
SECTION_KEYS = [k for k, _, _ in SECTIONS]
LEVELS = ("none", "view", "edit")
RANK = {"none": 0, "view": 1, "edit": 2, "delete": 3}

# ready-made sets to start from; each can then be changed
PRESETS = {
    "viewer": {"label": "Viewer", "help": "Sees reports, the Overview and documents — changes nothing.",
               "sections": {"home": "view", "departments": "view", "overview": "view", "documents": "view",
                            "comments": "view", "calendar": "view", "flow": "view", "updates": "view"},
               "delete": False},
    "reviewer": {"label": "Reviewer", "help": "Viewer, and adds comments to departments.",
                 "sections": {"home": "view", "departments": "view", "overview": "view", "documents": "view",
                              "comments": "edit", "calendar": "view", "flow": "view", "updates": "view"},
                 "delete": False},
    "coordinator": {"label": "Coordinator", "help": "Reviewer, and sends stages back, unlocks them, marks updates seen.",
                    "sections": {"home": "view", "departments": "view", "overview": "edit", "documents": "edit",
                                 "comments": "edit", "calendar": "view", "flow": "view", "updates": "edit"},
                    "delete": False},
    "full": {"label": "Full admin", "help": "Everything, including Settings and the team.", "full": True},
}

# admin endpoint -> (section, what it needs). A tuple of two needs is (GET, POST).
ENDPOINTS = {
    "dashboard": ("home", "view"), "analysis_report": ("home", "view"), "motion": ("home", "view"),
    "departments": ("departments", "view"),
    "department_form": ("departments", "edit"), "department_toggle": ("departments", "edit"),
    "generate_credentials": ("departments", "edit"), "credential_slip": ("departments", "edit"),
    "bulk_credentials": ("departments", "edit"), "credential_sheet": ("departments", "edit"),
    "import_departments": ("departments", "edit"), "import_commit": ("departments", "edit"),
    "pack_load": ("departments", "edit"), "demo_department": ("departments", "edit"),
    "demo_department_remove": ("departments", "delete"),
    "wipe_department": ("departments", "delete"),
    "submissions": ("overview", "view"), "analysis": ("overview", "view"),
    "submission_detail": ("overview", "view"), "submission_review": ("overview", "view"),
    "mark_seen": ("overview", "edit"), "submission_return": ("overview", "edit"),
    "submission_unlock": ("overview", "edit"),
    "export_institution": ("overview", "view"), "export_department": ("overview", "view"),
    "export_department_word": ("overview", "view"), "export_preview": ("overview", "view"),
    "programme_report": ("overview", "view"), "programme_docx": ("overview", "view"),
    "sheets_excel": ("overview", "view"),
    "document": ("documents", "view"), "document_summary": ("documents", "view"),
    "comment_add": ("comments", "edit"), "comment_close": ("comments", "edit"),
    "comments_json": ("comments", "view"),
    "calendar": ("calendar", "view"),
    "flow": ("flow", "view"), "flow_data": ("flow", "view"), "flow_excel": ("flow", "view"),
    "updates": ("updates", "view"), "updates_json": ("updates", "view"), "updates_read": ("updates", "edit"),
    "app_settings": ("settings", ("view", "edit")), "rules": ("settings", ("view", "edit")),
    "rules_reset": ("settings", "edit"), "audit_log": ("settings", "view"),
    "connectors": ("settings", ("view", "edit")), "connector_toggle": ("settings", "edit"),
    "connector_delete": ("settings", "delete"), "connector_test": ("settings", "edit"),
    "keywords": ("settings", ("view", "edit")), "keywords_reset": ("settings", "edit"),
    "keywords_recheck": ("settings", "edit"),
}
# Overview's sheet tabs belong to the menu item that opens them
SHEET_TABS = {"documents": "documents", "comments": "comments"}


def is_full(user: dict | None) -> bool:
    """The first admin, and anyone given Full admin, may do everything."""
    if not user or user.get("role") != "admin":
        return False
    return bool(user.get("full")) or not user.get("team")


def level(user: dict | None, section: str) -> str:
    if is_full(user):
        return "edit"
    if not user or user.get("role") != "admin":
        return "none"
    return ((user.get("access") or {}).get("sections") or {}).get(section) or "none"


def allows(user: dict | None, section: str, need: str = "view") -> bool:
    if is_full(user):
        return True
    have = level(user, section)
    if need == "delete":
        return have == "edit" and bool((user.get("access") or {}).get("delete"))
    return RANK.get(have, 0) >= RANK.get(need, 1)


def scope_codes(user: dict | None, db=None):
    """The department codes a user may see, or None for every department."""
    if is_full(user) or not user:
        return None
    sc = user.get("scope") or {}
    if sc.get("all", True):
        return None
    if db is None:
        from .db import get_db
        db = get_db()
    codes = set(sc.get("codes") or [])
    ors = []
    if sc.get("schools"):
        ors.append({"school": {"$in": sc["schools"]}})
    if sc.get("campuses"):
        ors.append({"campus": {"$in": sc["campuses"]}})
    if ors:
        codes |= {d["dept_code"] for d in db.departments.find({"$or": ors}, {"dept_code": 1})}
    return codes


def scope_q(field: str = "dept_code"):
    """A database filter for the current user's departments ({} for all)."""
    codes = current_scope()
    return {} if codes is None else {field: {"$in": sorted(codes)}}


def may_see(dept_code) -> bool:
    codes = current_scope()
    return codes is None or dept_code in codes


def current_user():
    """The signed-in admin's record, fresh from the database once a request:
    a change to someone's access applies from their next click."""
    if "access_user" in g:
        return g.access_user
    u = session.get("user") or {}
    rec = None
    if u.get("role") == "admin":
        from .db import get_db
        rec = get_db().users.find_one({"username": u.get("username"), "role": "admin"})
        if rec is not None and not rec.get("active", True):
            rec = None
    g.access_user = rec
    return rec


def current_scope():
    if "access_scope" not in g:
        g.access_scope = scope_codes(current_user())
    return g.access_scope


def summary(user: dict) -> str:
    """One line for the list and the slip: what, and for whom."""
    if is_full(user):
        what = "Full admin"
    else:
        acc = (user.get("access") or {}).get("sections") or {}
        named = next((p["label"] for k, p in PRESETS.items() if k != "full"
                      and all((acc.get(s) or "none") == (p["sections"].get(s) or "none") for s in SECTION_KEYS)
                      and bool((user.get("access") or {}).get("delete")) == p["delete"]), None)
        edits = [lbl for k, lbl, _ in SECTIONS if acc.get(k) == "edit"]
        views = [lbl for k, lbl, _ in SECTIONS if acc.get(k) == "view"]
        what = named or ("Custom — " + "; ".join(x for x in (
            ("edit: " + ", ".join(edits)) if edits else "", ("view: " + ", ".join(views)) if views else "") if x))
        if (user.get("access") or {}).get("delete"):
            what += " · can delete"
    sc = user.get("scope") or {}
    if is_full(user) or sc.get("all", True):
        whom = "all departments"
    else:
        parts = []
        if sc.get("schools"):
            parts.append(", ".join(sc["schools"]))
        if sc.get("campuses"):
            parts.append(", ".join(sc["campuses"]))
        if sc.get("codes"):
            parts.append(f"{len(sc['codes'])} department{'s' if len(sc['codes']) != 1 else ''}")
        whom = " + ".join(parts) or "no departments"
    return f"{what} · {whom}"


def guard_admin_request():
    """Before every admin page: is this section, and this department, the
    signed-in user's to open?"""
    from flask import flash, redirect, url_for
    u = session.get("user") or {}
    if u.get("role") != "admin":
        return None                      # admin_required sends them on their way
    me = current_user()
    if me is None:
        # disabled or removed while signed in: signed out at the next click
        session.pop("user", None)
        flash("Your access to the portal has been withdrawn. Ask the Office of Academic Affairs if this is a mistake.",
              "error")
        return redirect(url_for("auth.login"))
    # a team member given a password by the Office sets their own first
    if me.get("team") and me.get("must_change"):
        flash("Please set your own password before you carry on.", "info")
        return redirect(url_for("auth.change_password"))
    ep = (request.endpoint or "").split(".", 1)[-1]
    if ep.startswith("team"):
        if not is_full(me):
            abort(403)
    elif ep == "sheets":
        if not allows(me, SHEET_TABS.get(request.args.get("tab"), "overview"), "view"):
            abort(403)
    elif ep != "static":
        rule = ENDPOINTS.get(ep)
        if rule is None:
            if not is_full(me):
                abort(403)
        else:
            section, need = rule
            if isinstance(need, tuple):
                need = need[0] if request.method == "GET" else need[1]
            elif request.method == "POST" and need == "view" and ep != "document_summary":
                need = "edit"
            if not allows(me, section, need):
                abort(403)
    for code in ((request.view_args or {}).get("dept_code"), request.args.get("dept")):
        if code and not may_see(code):
            abort(403)
    return None


# where each section's menu item goes
SECTION_HOME = {"home": ("admin.dashboard", {}), "departments": ("admin.departments", {}),
                "overview": ("admin.submissions", {}), "documents": ("admin.sheets", {"tab": "documents"}),
                "comments": ("admin.sheets", {"tab": "comments"}), "calendar": ("admin.calendar", {}),
                "flow": ("admin.flow", {}), "updates": ("admin.updates", {}), "settings": ("admin.app_settings", {})}


def home_url(user=None):
    """Where an admin lands: the home, or else the first section they may open."""
    from flask import url_for
    user = user if user is not None else current_user()
    for key in SECTION_KEYS:
        if allows(user, key, "view"):
            ep, args = SECTION_HOME[key]
            return url_for(ep, **args)
    return url_for("auth.change_password")


def template_helpers():
    """can('overview'), can('comments', 'edit'), and is_full_admin, for the
    menu and the pages."""
    def can(section, need="view"):
        return allows(current_user(), section, need)
    return {"can": can, "is_full_admin": lambda: is_full(current_user()), "admin_home": home_url}
