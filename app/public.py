"""Public landing page and campus information."""

from flask import Blueprint, render_template

from .db import get_db

bp = Blueprint("public", __name__)

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


@bp.route("/")
def landing():
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
    return render_template("landing.html", campuses=CAMPUS_INFO, stats=stats,
                           per_campus=per_campus)


@bp.route("/about")
def about():
    return render_template("about.html", campuses=CAMPUS_INFO)
