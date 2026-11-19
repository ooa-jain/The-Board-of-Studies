"""Public pages: the sign-in page and Help."""

import json

from flask import (Blueprint, abort, current_app, redirect, render_template, request, send_from_directory,
                   session, url_for)

from .db import get_db, settings
from .workflow import get_or_create_submission, next_action, progress

bp = Blueprint("public", __name__)



# ---------------------------------------------------------------- the app
# The portal installs as an app (a PWA): the manifest names it and its icon,
# and the service worker lets it open on its own. Both are served from the
# site's root, where a service worker must live to look after every page.

@bp.route("/manifest.webmanifest")
def manifest():
    # only the Office installs the portal as an app
    user = session.get("user") or {}
    if user.get("role") != "admin":
        abort(404)
    data = {
        "id": "/",
        "name": "BoS Academic Portal",
        "short_name": "BoS Portal",
        "description": "JAIN Office of Academic Affairs — Board of Studies records.",
        "start_url": "/?app=1",
        "scope": "/",
        "display": "standalone",
        "background_color": "#091324",
        "theme_color": "#091324",
        "icons": [
            {"src": url_for("static", filename="img/app-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": url_for("static", filename="img/app-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": url_for("static", filename="img/app-maskable-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    # long-press the app icon: straight to these
    data["shortcuts"] = [
        {"name": "Departments", "url": url_for("admin.overview_departments")},
        {"name": "Updates", "url": url_for("admin.updates")},
        {"name": "Storage", "url": url_for("admin.storage")},
    ]
    resp = current_app.response_class(json.dumps(data), mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript",
                               max_age=0)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/")
def landing():
    # a signed-in department's home is its submission page
    user = session.get("user") or {}
    if user.get("role") == "department" and user.get("dept_code"):
        return redirect(url_for("dept.dashboard"))
    if user.get("role") == "admin":
        from .access import home_url
        return redirect(home_url())
    db = get_db()
    # somewhere behind a login sent us here; the form carries it back
    nxt = request.args.get("next")
    if not (nxt or "").startswith("/"):
        nxt = None
    # Only what the page actually prints. The per-school breakdown used to be
    # listed here and cost one count query per school; it is gone, and so is
    # the counting.
    stats = {"departments": db.departments.count_documents({"active": True})}
    # the sign-in page is a page of its own: no top bar, no footer
    from pathlib import Path
    folder = Path(current_app.static_folder) / "video"
    intro = {n: int((folder / n).stat().st_mtime) if (folder / n).is_file() else 0
             for n in ("intro.mp4", "intro.jpg")}
    return render_template("landing.html", stats=stats, next_url=nxt, intro=intro,
                           resume=_resume_for(session.get("user")), hide_chrome=True)


def _resume_for(user):
    """Where a signed-in department had got to, for the home page.

    Somebody already signed in who comes back to the home page does not want
    to be asked to sign in again — they want the thread they dropped. This is
    that thread: how far through they are, and the one stage to open next.
    """
    if not user or user.get("role") != "department" or not user.get("dept_code"):
        return None

    db = get_db()
    dept = db.departments.find_one({"dept_code": user["dept_code"]})
    if not dept:
        return None

    year = settings().get("academic_year") or current_app.config["ACADEMIC_YEAR"]
    sub = get_or_create_submission(user["dept_code"], year)
    return {
        "dept": dept,
        "year": year,
        "progress": progress(sub),
        "next": next_action(sub),
        "sealed": sub.get("status") == "sealed",
    }




def help_media():
    """The Help walkthrough's sections and the help files, each with its date
    as a version so a new video or manual is not served from a stale cache."""
    import json
    from pathlib import Path
    folder = Path(current_app.static_folder) / "help"
    try:
        chapters = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        chapters = []
    files = {n: int((folder / n).stat().st_mtime) if (folder / n).is_file() else 0
             for n in ("walkthrough.mp4", "manual.pdf", "poster.jpg")}
    return chapters, files


@bp.route("/help")
def help_public():
    """Help without signing in: the walkthrough video, section by section, and
    the user manual — the same as a department's Help page."""
    chapters, files = help_media()
    return render_template("dept/help.html", dept=None, chapters=chapters, files=files)


@bp.route("/about")
def about():
    """The About page is gone; an old link to it lands on Help."""
    return redirect(url_for("public.help_public"), code=301)
