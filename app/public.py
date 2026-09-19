"""Public landing page and campus information."""

from flask import Blueprint, render_template, request

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
    # somewhere behind a login sent us here; the form carries it back
    nxt = request.args.get("next")
    if not (nxt or "").startswith("/"):
        nxt = None
    # Only what the page actually prints. The per-school breakdown used to be
    # listed here and cost one count query per school; it is gone, and so is
    # the counting.
    stats = {"departments": db.departments.count_documents({"active": True})}
    return render_template("landing.html", stats=stats, next_url=nxt)


# What a department actually hands over, and the stage it hands it over at.
# Drawn from the schema's file fields, in the order they are asked for.
FILINGS = [
    {"name": "DIAC composition, signed", "stage": "Pre-BoS"},
    {"name": "Board of Studies composition, signed", "stage": "Pre-BoS"},
    {"name": "PAC composition, signed", "stage": "Pre-BoS"},
    {"name": "Meeting agenda and minutes", "stage": "Meeting Documents"},
    {"name": "Approved BoS file", "stage": "Final BoS Repository"},
    {"name": "Consolidated PDF of everything", "stage": "Final BoS Repository"},
]


@bp.route("/about")
def about():
    return render_template("about.html", campuses=CAMPUS_INFO, filings=FILINGS)
