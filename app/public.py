"""Public landing page and campus information."""

from flask import Blueprint, current_app, render_template, request, session

from .db import get_db, settings
from .workflow import get_or_create_submission, next_action, progress

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
    return render_template("landing.html", stats=stats, next_url=nxt,
                           resume=_resume_for(session.get("user")))


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
