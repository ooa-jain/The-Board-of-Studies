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
    return render_template("landing.html", stats=stats, next_url=nxt, intro=intro_media(),
                           resume=_resume_for(session.get("user")), hide_chrome=True)


# the intro film in each language: English first (the default), then the rest
INTRO_LANGS = (("en", "English", "intro.mp4"), ("hi", "हिन्दी", "intro-hi.mp4"),
               ("kn", "ಕನ್ನಡ", "intro-kn.mp4"), ("ta", "தமிழ்", "intro-ta.mp4"),
               ("ml", "മലയാളം", "intro-ml.mp4"))


def intro_media():
    """The intro film: its still, and one file per language that is there,
    each with its date as a version. None when there is no English film."""
    from pathlib import Path
    folder = Path(current_app.static_folder) / "video"

    def ver(n):
        f = folder / n
        return int(f.stat().st_mtime) if f.is_file() else 0

    langs = [{"code": c, "label": lab, "src": url_for("static", filename=f"video/{n}", v=ver(n))}
             for c, lab, n in INTRO_LANGS if ver(n)]
    if not langs or langs[0]["code"] != "en":
        return None
    from .auth import page_user
    from .i18n import current_lang
    want = current_lang(page_user())
    first = next((l for l in langs if l["code"] == want), langs[0])
    for l in langs:
        l["on"] = l is first
    return {"src": first["src"], "langs": langs,
            "poster": url_for("static", filename="video/intro.jpg", v=ver("intro.jpg"))}


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


@bp.post("/language")
def set_language():
    """The language picked in the profile menu: kept in this browser for a
    year, then back to the page it was picked on."""
    from .i18n import CODES, COOKIE
    code = request.form.get("lang", "en")
    nxt = request.form.get("next") or "/"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    resp = redirect(nxt)
    if code in CODES:
        resp.set_cookie(COOKIE, code, max_age=365 * 24 * 3600, samesite="Lax",
                        secure=request.is_secure, httponly=False)
    return resp


@bp.route("/i18n/<code>.js")
def i18n_words(code):
    """One language's words, as a script the page loads before it draws."""
    from .i18n import CODES, words
    if code not in CODES or code == "en":
        abort(404)
    body = "window.BOS_I18N=" + json.dumps(words(code), ensure_ascii=False, separators=(",", ":")) + ";"
    resp = current_app.response_class(body, mimetype="application/javascript")
    resp.cache_control.public = True
    resp.cache_control.max_age = 7 * 24 * 3600
    return resp


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
