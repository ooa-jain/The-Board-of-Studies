"""Public landing page and campus information."""

import json

from flask import (Blueprint, abort, current_app, redirect, render_template, request, send_from_directory,
                   session, url_for)

from .db import get_db, settings
from .workflow import get_or_create_submission, next_action, progress

bp = Blueprint("public", __name__)

CAMPUS_INFO = [
    {
        "name": "Bengaluru",
        "state": "Karnataka",
        "blurb": "The principal campus of JAIN (Deemed-to-be University), and the seat of the "
                 "Office of Academic Affairs. Schools across commerce, management, engineering, "
                 "sciences, humanities and law submit their Board of Studies records here.",
        "art": "bengaluru",
        "accent": "#C8A44B",
    },
    {
        "name": "Kochi",
        "state": "Kerala",
        "blurb": "The Kochi campus follows the same Board of Studies calendar and the same "
                 "UGC credit framework. Departments here submit through this portal on the "
                 "identical stage sequence.",
        "art": "kochi",
        "accent": "#4BA3C8",
    },
]


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
    return render_template("landing.html", stats=stats, next_url=nxt,
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


# What a department actually hands over, and the stage it hands it over at.
# Drawn from the schema's file fields, in the order they are asked for.
FILINGS = [
    {"name": "DIAC composition, signed", "stage": "Pre-BoS"},
    {"name": "DPAC composition, signed", "stage": "Pre-BoS"},
    {"name": "BoS composition, vision and mission, minutes", "stage": "BoS Documents"},
    {"name": "Geotagged photos, attendance, external profiles", "stage": "BoS Documents"},
    {"name": "Stakeholder feedback", "stage": "BoS Documents"},
    {"name": "Curriculum, syllabus and revision log per programme", "stage": "Curriculum"},
]


@bp.route("/about")
def about():
    return render_template("about.html", campuses=CAMPUS_INFO, filings=FILINGS)
