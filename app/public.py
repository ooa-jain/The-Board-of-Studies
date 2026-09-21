"""Public landing page and campus information.

The landing page is an introduction, not a doorway. It is shown to a visitor
who has not seen it before; after that the portal opens straight on the thing
that person actually came for — their dashboard if they are signed in, the
sign-in screen if they are not. ``?home=1`` (the "portal home" links in the
chrome) always shows it in full, so nothing is ever unreachable.
"""

from __future__ import annotations

from flask import (Blueprint, current_app, make_response, redirect,
                   render_template, request, session, url_for)

from .db import get_db

bp = Blueprint("public", __name__)

#: Set once the landing page has been served. Its only job is to remember that
#: the introduction has been read; it carries no identity and no state.
SEEN_COOKIE = "bos_intro_seen"

CAMPUS_INFO = [
    {
        "name": "Bengaluru",
        "state": "Karnataka",
        "blurb": "The principal campus of JAIN (Deemed-to-be University), and the seat of the "
                 "Office of Academics. Schools across commerce, management, engineering, "
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


def home_url_for(user) -> str:
    """Where “home” goes for whoever is asking."""
    if user and user.get("role") == "admin":
        return url_for("admin.dashboard")
    if user and user.get("role") == "department":
        return url_for("dept.dashboard")
    return url_for("auth.login")


@bp.route("/")
def landing():
    user = session.get("user")
    forced = request.args.get("home") == "1"

    # Signed in: the introduction is behind them, whatever the cookie says.
    # Clicking the masthead should land on their own work, not on a brochure.
    if user and not forced:
        return redirect(home_url_for(user))

    # Seen it once already: go where they were going.
    if not forced and request.cookies.get(SEEN_COOKIE):
        return redirect(url_for("auth.login"))

    db = get_db()
    stats = {
        "departments": db.departments.count_documents({"active": True}),
        "schools": len(db.departments.distinct("school", {"active": True})),
        "campuses": len(db.departments.distinct("campus", {"active": True})) or 2,
        "submitted": db.submissions.count_documents({"status": {"$in": ["submitted", "sealed"]}}),
    }
    per_campus = {}
    for c in CAMPUS_INFO:
        per_campus[c["name"]] = db.departments.count_documents(
            {"campus": c["name"], "active": True})

    response = make_response(render_template(
        "landing.html", campuses=CAMPUS_INFO, stats=stats, per_campus=per_campus,
        revisit=forced and bool(request.cookies.get(SEEN_COOKIE))))
    days = current_app.config.get("LANDING_SEEN_DAYS", 180)
    response.set_cookie(
        SEEN_COOKIE, "1",
        max_age=days * 24 * 60 * 60,
        samesite="Lax",
        httponly=True,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )
    return response


@bp.route("/about")
def about():
    return render_template("about.html", campuses=CAMPUS_INFO)
