"""
"Fill from Drive" — one press on a department's dashboard fills everything.

For a department that has a data pack (app/pack_data/, from its Drive folder)
this loads the pack — its course matrices, syllabi and files — and then goes
through every stage and every programme part and fills what the Drive folder
did not cover, with entries that suit, so each stage is ready to review and
submit:

    Department Information   the catalogue's programmes and the department's record
    Pre-BoS                  the DIAC and DPAC composition forms, in the university's
                             templates, one member for each category
    BoS Documents            the meeting date, composition, minutes, attendance,
                             external profiles, photos, vision and mission, feedback
    each programme           regulations (intake, eligibility), a programme
                             structure when the Drive has no matrix for it, the
                             syllabus rows (pedagogy, hours, outcomes, modules,
                             activities, books) and the Course Revision

Everything it adds is marked as such — names read "name to be confirmed" and
the documents say they are filled in by the portal — so nothing passes for the
department's own signed paper. What the Drive folder supplied is never changed,
and a stage that is already submitted is left alone. The stages are saved as
drafts: the department reviews them and presses Submit.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path

from flask import current_app

from . import demo_dept
from .db import get_db, now
from .keyword_match import check as keyword_check
from .packs import PARTS, find_department, get_pack, load_pack
from .schema import PARTS as PROGRAMME_PARTS
from .schema import STAGE_BY_KEY, STAGE_KEYS, degree_years, programme_level
from .summarise import field_label
from .template_check import TEMPLATES, fill, make_bos_composition
from .workflow import (course_fill_source, get_or_create_submission, prefill_for,
                       programme_stage_state, programmes_of, revision_fill_source, save_draft)

NOTE = "Filled in by the portal from the Drive folder — replace with the signed original."
BOS_DATE = "2026-06-25"

# who sits on the DIAC, DPAC and BoS: a seat for every category, not a person
def _seat(role):
    return (f"{role} — name to be confirmed", role)


PEOPLE = {c: _seat(c.split(" /")[0]) for t in ("diac_signed", "dpac_signed")
          for c, _ in TEMPLATES[t]["categories"]}

# ---------------------------------------------------------------------------
# programme content, where the Drive has none
# ---------------------------------------------------------------------------

UG_TOPICS = {
    "Major (Core)": ["Programming Fundamentals", "Discrete Mathematics", "Computer Organisation",
                     "Data Structures", "Database Management Systems", "Operating Systems",
                     "Object Oriented Programming", "Computer Networks", "Software Engineering",
                     "Web Technologies", "Design and Analysis of Algorithms", "Artificial Intelligence",
                     "Machine Learning", "Cloud Computing", "Cyber Security", "Mobile Application Development",
                     "Data Analytics", "Internet of Things", "Big Data Technologies", "Capstone Studio"],
    "Minor Stream": ["Introduction to Analytics", "Statistics for Computing", "Digital Marketing",
                     "Business Fundamentals", "Design Thinking", "Information Systems",
                     "Project Management", "Professional Practice"],
    "Multidisciplinary": ["Environmental Studies", "Indian Economy", "Psychology at Work"],
    "Ability Enhancement Courses (AEC)": ["English Communication I", "English Communication II",
                                          "Language I", "Language II"],
    "Skill Enhancement Courses (SEC)": ["Spreadsheet Skills", "Data Visualisation", "Version Control and DevOps"],
    "Value Added Courses (VAC)": ["Indian Constitution", "Yoga and Wellbeing", "Professional Ethics",
                                  "Sustainability and Design Thinking"],
    "Summer Internship": ["Summer Internship"],
    "Research Project / Dissertation": ["Research Project / Dissertation"],
}
# (group, credits, L, E, how many) — a 4-year Honours with Research programme meeting UGC Table 2
UG_PLAN = [("Major (Core)", 4, 4, 0, 20), ("Minor Stream", 4, 4, 0, 8),
           ("Multidisciplinary", 3, 3, 0, 3), ("Ability Enhancement Courses (AEC)", 2, 2, 0, 4),
           ("Skill Enhancement Courses (SEC)", 3, 3, 0, 3), ("Value Added Courses (VAC)", 2, 2, 0, 4),
           ("Summer Internship", 2, 0, 6, 1), ("Research Project / Dissertation", 12, 8, 12, 1)]
PG_TOPICS = ["Advanced Data Structures", "Advanced Database Systems", "Advanced Computer Networks",
             "Software Engineering Practices", "Cloud and Virtualisation", "Machine Learning",
             "Research Methodology", "Information Security", "Distributed Systems", "Big Data Analytics",
             "Web and Mobile Application Development", "Natural Language Processing",
             "Deep Learning", "Blockchain Technologies", "Software Quality Assurance",
             "Data Mining", "Internet of Things", "DevOps and Automation", "Computer Vision",
             "Professional Ethics and Practice"]


LETTER = {"Major (Core)": "C", "Minor Stream": "M", "Multidisciplinary": "O",
          "Ability Enhancement Courses (AEC)": "A", "Skill Enhancement Courses (SEC)": "S",
          "Value Added Courses (VAC)": "V", "Summer Internship": "I", "Research Project / Dissertation": "R"}


def _ug_courses(prefix):
    rows, per_sem, n = [], {}, 0
    for group, credits, lec, exp, count in UG_PLAN:
        for i in range(count):
            n += 1
            sem = {"Summer Internship": 6, "Research Project / Dissertation": 8}.get(group) \
                or (n - 1) % 6 + 1
            if group == "Major (Core)" and n > 14:           # the later major courses in the honours years
                sem = 7 + (n % 2)
            per_sem[sem] = per_sem.get(sem, 0) + 1
            titles = UG_TOPICS[group]
            rows.append({"semester": sem, "track": ("Honours with Research" if sem >= 7 and
                                                    group == "Research Project / Dissertation"
                                                    else "All semesters"),
                         "nep_category": group,
                         "course_code": f"26{prefix}{sem}{LETTER[group]}{per_sem[sem]:02d}",
                         "course_title": titles[i % len(titles)],
                         "l": lec, "t": 0, "p": 0, "e": exp, "credits": credits,
                         "cia": 50, "ese": 50, "total_marks": 100})
    rows.sort(key=lambda r: (r["semester"], r["course_code"]))
    return rows


def _pg_courses(prefix):
    rows = []
    n = 0
    for sem in range(1, 5):
        count = 5 if sem < 4 else 3
        for i in range(count):
            title = PG_TOPICS[n % len(PG_TOPICS)]
            n += 1
            # the PG Course Matrix's classifications
            group = ("Generic Core" if i < 2 else "Specialisation Core" if i < 4
                     else "Generic Elective" if sem == 1 else "Specialisation Elective")
            rows.append({"semester": sem,
                         "nep_category": group,
                         "course_code": f"26{prefix}{sem}{'C' if 'Core' in group else 'E'}{i + 1:02d}",
                         "course_title": title, "l": 4, "t": 0, "p": 0, "e": 0, "credits": 4,
                         "cia": 60, "ese": 40, "total_marks": 100})
        if sem < 4:
            rows.append({"semester": sem, "nep_category": "Open Elective" if sem == 3 else "Generic Core",
                         "course_code": f"26{prefix}{sem}S01", "course_title": f"Skill Lab {sem}",
                         "l": 3, "t": 0, "p": 0, "e": 0, "credits": 3, "cia": 100, "ese": 0, "total_marks": 100})
    rows.append({"semester": 4, "nep_category": "Research / Thesis / Project / Patent",
                 "course_code": f"26{prefix}4P01", "course_title": "Project / Internship",
                 "l": 2, "t": 0, "p": 4, "e": 12, "credits": 8, "cia": 60, "ese": 40, "total_marks": 100})
    return rows


EXPECTED_ELIGIBILITY = {
    "UG": "A pass in Level 4 / Class 12 schooling (formal or open school) or its equivalent, with "
          "Mathematics / Computer Science as one of the subjects, from a recognised board.",
    "PG": "A bachelor's degree in computer applications, computer science, IT or an allied discipline "
          "(or any bachelor's degree with Mathematics at Class 12), with a minimum of 50% marks.",
}
PEDAGOGY = ("Classroom lectures, case studies, tutorial classes, group discussion, seminars, "
            "hands-on laboratory work and projects.")
BOOKS = ("1. Core text of the discipline, latest edition, Pearson Education.\n"
         "2. Reference text on the subject, latest edition, McGraw Hill Education.\n"
         "3. Course handbook and online resources prescribed by the department.")
ACTIVITIES = ("1. Prepare a short report on a real-world application of the course topics.\n"
              "2. Build a small working demonstration of one module and present it in class.\n"
              "3. Any other activity relevant to the course, as set by the faculty.")
OUTCOMES = ("Understand the fundamental concepts of {t}.\n"
            "Apply the techniques of {t} to solve problems.\n"
            "Analyse problems and select suitable methods from {t}.\n"
            "Develop small solutions using the tools and practices of {t}.\n"
            "Evaluate the results and limitations of the approaches studied.")
MODULES = [("Foundations", 9), ("Core concepts", 9), ("Techniques and methods", 9),
           ("Tools and practice", 9), ("Applications and case studies", 9)]


def _module_rows(title):
    return [{"title": name, "hours": hrs, "previous": "", "pct": None,
             "revised": f"{name} of {title}: key concepts, worked examples and exercises."}
            for name, hrs in MODULES]


# ---------------------------------------------------------------------------
# a programme's parts
# ---------------------------------------------------------------------------

def _is_submitted(sub, code, part):
    return programme_stage_state(sub, code, part).get("status") == "submitted"


def _major_from_syllabus(courses, pg=False):
    """The programme's major courses as the Drive's syllabus lists them (a PG
    programme assesses 60 / 40)."""
    rows = []
    for c in courses:
        credits = int(float(c.get("credits") or 3))
        lab = "lab" in str(c.get("course_title") or "").lower()
        rows.append({"semester": int(c.get("semester") or 1), "track": "All semesters",
                     "nep_category": "Major (Core)", "course_code": c["course_code"],
                     "course_title": c.get("course_title") or "", "l": 0 if lab else credits, "t": 0,
                     "p": credits * 2 if lab else 0, "e": 0, "credits": credits,
                     "cia": 100 if lab else (60 if pg else 50), "ese": 0 if lab else (40 if pg else 50),
                     "total_marks": 100})
    return rows


def _curriculum(dept, programme, sub, year, stored, syllabus_courses=()):
    code = programme["programme_code"]
    prefix = re.sub(r"[^A-Z]", "", code.upper())[:5] or "CS"
    data = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (stored or {}).items()}
    details = data.setdefault("details", {})
    ug = programme_level(details.get("degree_level") or programme.get("degree_level")) == "UG" \
        if (details.get("degree_level") or programme.get("degree_level")) else programme.get("level") != "PG"
    if not details.get("degree_level"):
        details["degree_level"] = ("UG - 4 Year (Honours with Research)" if ug else "PG - 2 Year")
    if not data.get("semester_structure"):
        rows = _ug_courses(prefix) if ug else _pg_courses(prefix)
        if syllabus_courses:
            # the syllabus is the Drive's: its courses are the major, the rest fills the scheme
            rows = _major_from_syllabus(syllabus_courses, pg=not ug) + [
                r for r in rows if r["nep_category"] not in ("Major (Core)", "Generic Core", "Specialisation Core")]
        data["semester_structure"] = rows
    if not ug:
        # a PG programme's groups in the PG Course Matrix's terms, whatever the pack called them
        from .schema import pg_groups
        data = pg_groups(data, details["degree_level"])
        details = data["details"]
    profile = data.setdefault("profile", {})
    prog_name = programme.get("programme_name") or code
    profile.setdefault("objective",
                       f"To build sound knowledge and practical skills in {prog_name}.\n"
                       "To prepare students for careers in the computing industry and for higher study.\n"
                       "To develop ethical, communication and teamwork skills.")
    years = degree_years(details["degree_level"]) or (4 if ug else 2)
    profile.setdefault("duration_months", years * 12)
    profile.setdefault("intake", 60)
    profile.setdefault("eligibility", EXPECTED_ELIGIBILITY["UG" if ug else "PG"])
    profile.setdefault("course_specialisation", prog_name)
    for k, v in list(profile.items()):
        if v in (None, ""):
            del profile[k]
    if not [m for m in data.get("minors") or [] if isinstance(m, dict)]:
        data["minors"] = _minors(data["semester_structure"], ug)
    return data


MINOR_STREAMS = [("Data Analytics", ["Introduction to Data Analytics", "Statistics for Data Science",
                                     "Data Visualisation", "Predictive Analytics"]),
                 ("Cyber Security", ["Foundations of Cyber Security", "Network Security",
                                     "Ethical Hacking", "Digital Forensics"])]


def _minors(structure, ug):
    """Annexure I: the minor streams a student can take, from the structure's
    minor courses where it has them."""
    picked = [r for r in structure if r.get("nep_category") == ("Minor Stream" if ug
                                                                else "Discipline Specific Elective (DSE)")]
    if picked:
        stream = "Minor stream" if ug else "Discipline electives (Honours basket)"
        return [{"minor_title": stream, "semester": r.get("semester"), "course_code": r.get("course_code"),
                 "course_title": r.get("course_title"), "credits": r.get("credits")} for r in picked]
    out = []
    for n, (stream, titles) in enumerate(MINOR_STREAMS, 1):
        for i, t in enumerate(titles, 1):
            out.append({"minor_title": stream, "semester": i + 2, "course_code": f"26MN{n}{i + 2}{i:02d}",
                        "course_title": t, "credits": 4})
    return out


def _syllabus(sub, programme, stored, year):
    code = programme["programme_code"]
    data = dict(stored or {})
    courses = [c for c in (data.get("courses") or []) if isinstance(c, dict)]
    if not courses:
        courses = [dict(c) for c in course_fill_source(sub, code)]
    out, used = [], {str(c.get("course_code") or "").strip().upper() for c in courses}
    prefix = re.sub(r"[^A-Z]", "", code.upper())[:5] or "CS"
    for n, c in enumerate(courses, 1):
        c = dict(c)
        if not str(c.get("course_code") or "").strip():
            # the Drive's syllabus gives the title but no code: a unique one, to be replaced
            k = n
            while f"26{prefix}{c.get('semester') or 1}X{k:02d}" in used:
                k += 1
            c["course_code"] = f"26{prefix}{c.get('semester') or 1}X{k:02d}"
            used.add(c["course_code"].upper())
        title = c.get("course_title") or "the course"
        credits = c.get("credits") or 3
        c.setdefault("credits", credits)
        if c.get("hours_per_week") in (None, ""):
            c["hours_per_week"] = int(float(credits)) if float(credits) >= 1 else 1
        if c.get("teaching_hours") in (None, "") or int(float(c.get("teaching_hours") or 0)) < 10:
            c["teaching_hours"] = int(round(float(credits) * 15))
        if not str(c.get("pedagogy") or "").strip():
            c["pedagogy"] = PEDAGOGY
        if not str(c.get("outcomes") or "").strip():
            c["outcomes"] = OUTCOMES.format(t=title)
        if not [m for m in c.get("modules") or [] if str((m or {}).get("revised") or "").strip()]:
            c["modules"] = _module_rows(title)
        if not str(c.get("skill_activities") or "").strip():
            c["skill_activities"] = ACTIVITIES
        if len([x for x in str(c.get("books") or "").splitlines() if x.strip()]) < 2:
            c["books"] = (str(c.get("books") or "").strip() + "\n" + BOOKS).strip()
        out.append(c)
    data["courses"] = out
    return data


def _revision(sub, programme, stored, year):
    code = programme["programme_code"]
    data = dict(stored or {})
    rows = [dict(r) for r in (data.get("courses") or []) if isinstance(r, dict)]
    if not rows:
        rows = revision_fill_source(sub, code)
    out = []
    for r in rows:
        r = dict(r)
        if not [m for m in r.get("modules") or [] if str((m or {}).get("revised") or "").strip()]:
            r["modules"] = _module_rows(r.get("course_title") or "the course")
        mods = []
        for m in r["modules"]:
            m = dict(m or {})
            if m.get("pct") in (None, "") and str(m.get("revised") or "").strip():
                # no earlier syllabus of the course: all of it is new
                m["pct"] = 100 if not str(m.get("previous") or "").strip() else 0
            mods.append(m)
        r["modules"] = mods
        pcts = [float(m["pct"]) for m in mods if m.get("pct") not in (None, "")]
        if pcts and r.get("avg_change") in (None, ""):
            r["avg_change"] = round(sum(pcts) / len(pcts), 2)
        r.setdefault("year_latest", year[:4])
        out.append(r)
    data["courses"] = out
    return data


def _batch_syllabus(current, batch_label, stored):
    """An earlier batch's syllabus, where the Drive has none: the current
    batch's courses as a stand-in — the batch's year in the course codes,
    each course marked to be confirmed against what that batch was taught."""
    data = dict(stored or {})
    if [c for c in (data.get("courses") or []) if isinstance(c, dict) and c.get("course_title")]:
        return data
    yy = str(batch_label or "")[2:4]
    out = []
    for c in (current or {}).get("courses") or []:
        if not isinstance(c, dict):
            continue
        c = {k: (list(v) if isinstance(v, list) else v) for k, v in c.items()}
        code_ = str(c.get("course_code") or "")
        if yy.isdigit() and re.match(r"^\d{2}", code_):
            c["course_code"] = yy + code_[2:]
        mods = [dict(m or {}) for m in c.get("modules") or []]
        if mods:
            # the earlier batch read one module differently: so Course
            # Revision has a change to measure
            last = mods[-1]
            last["revised"] = (str(last.get("revised") or "").rstrip(". ") +
                               ". (As taught to the " + str(batch_label) + " batch — to be confirmed.)")
            c["modules"] = mods
        c["books"] = (str(c.get("books") or "").strip() + "\n" + NOTE).strip()
        out.append(c)
    data["courses"] = out
    return data


# ---------------------------------------------------------------------------
# the documents
# ---------------------------------------------------------------------------

def _store(db, dept_code, year, stage, field, name, writer, actor):
    folder = current_app.config["UPLOAD_ROOT"] / year / dept_code / stage
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}-{name}"
    path = folder / stored
    writer(path)
    match = keyword_check(path, field, field_label(stage, field))
    db.files.insert_one({"dept_code": dept_code, "academic_year": year, "stage": stage, "field": field,
                         "original_name": name, "stored_name": stored, "size": path.stat().st_size,
                         "uploaded_by": actor, "uploaded_at": now(), "keyword_match": match,
                         "autofilled": True})
    val = {"name": name, "stored": stored, "size": path.stat().st_size,
           "url": f"/department/file/{stage}/{stored}", "match": match}
    if name.lower().endswith(".pdf"):
        val["thumb"] = val["url"] + "?thumb=1"
    return val


def _photo(path, n, dept_name):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (640, 420), (14, 61, 124) if n == 1 else (31, 107, 68))
        d = ImageDraw.Draw(img)
        d.rectangle([20, 20, 620, 400], outline=(242, 169, 0), width=6)
        d.text((40, 40), f"BoS meeting photo {n} (sample)", fill=(255, 255, 255))
        d.text((40, 70), dept_name, fill=(255, 255, 255))
        img.save(path, "JPEG", quality=80)
    except Exception:
        demo_dept._photo(path, n)


def _documents(dept):
    name = dept["dept_name"]
    return {
        "vision_mission": ("Vision_Mission_PEO_PO.pdf", [
            f"{name} — Vision, Mission, PEOs and POs", NOTE,
            "Vision: to be a centre of excellence in computing education and research.",
            "Mission: to develop skilled, ethical and employable computing professionals.",
            "Programme Educational Objectives (PEO), Programme Outcomes (PO) and Programme Specific "
            "Outcomes (PSO) are listed for each programme."]),
        "minutes": ("Minutes_of_Meeting.pdf", [
            f"Minutes of the Board of Studies Meeting — {name}", NOTE,
            f"Meeting held on {BOS_DATE}; venue: the department. Agenda: course matrix and syllabus of the programmes.",
            "Members present: as in the attendance sheet.",
            "Resolved and approved: the curriculum, course matrix and syllabus for the coming batch.",
            "Observation and recommendation: keep the courses aligned with industry practice."]),
        "attendance": ("Attendance_Sheet.pdf", [
            f"Attendance Sheet — Board of Studies Meeting, {BOS_DATE}", NOTE,
            "S.No   Name   Designation   Signature",
            "1  Chairperson — name to be confirmed  Chairperson  (signature)",
            "2  External Member — name to be confirmed  External Expert  (signature)"]),
        "external_profiles": ("External_Expert_Profile.pdf", [
            "Profile of the external expert — name to be confirmed", NOTE,
            "Designation: Professor / Industry expert. Qualification: Ph.D / degree in computing.",
            "Experience: 15+ years. Publications and projects: as per CV. Email and contact: to be added."]),
        "feedback_curriculum": ("Stakeholder_Feedback.pdf", [
            f"Stakeholder feedback for the curriculum — {name}", NOTE,
            "Survey of students, alumni, industry and faculty by email and questionnaire.",
            "Feedback and suggestions: more hands-on work; recommendation to keep the curriculum "
            "and syllabus current with industry."]),
    }


def _bos_files(db, dept, year, actor, have):
    code, files = dept["dept_code"], {}

    def pdf(lines):
        return lambda path: path.write_bytes(demo_dept._pdf(lines))

    for field, (fname, lines) in _documents(dept).items():
        if field in have:
            files[field] = have[field]
            continue
        v = _store(db, code, year, "bos_documents", field, fname, pdf(lines), actor)
        files[field] = [v] if field in ("external_profiles", "feedback_curriculum") else v
    if "bos_composition" in have:
        files["bos_composition"] = have["bos_composition"]
    else:
        files["bos_composition"] = _store(db, code, year, "bos_documents", "bos_composition",
                                          "Composition_of_BoS_Members.docx",
                                          lambda path: make_bos_composition(path, PEOPLE), actor)
    if "geotagged_photos" in have:
        files["geotagged_photos"] = have["geotagged_photos"]
    else:
        files["geotagged_photos"] = [
            _store(db, code, year, "bos_documents", "geotagged_photos", f"meeting_photo_{n}.jpg",
                   lambda path, n=n: _photo(path, n, dept["dept_name"]), actor) for n in (1, 2)]
    return files


def _pre_bos_files(db, dept, year, actor, have):
    static = Path(__file__).resolve().parent / "static"
    out = {}
    for field, fname in (("diac_signed", "Composition_of_DIAC.docx"), ("dpac_signed", "Composition_of_DPAC.docx")):
        if field in have:
            out[field] = have[field]
            continue
        src = static / TEMPLATES[field]["file"]
        out[field] = _store(db, dept["dept_code"], year, "pre_bos", field, fname,
                            lambda path, src=src, field=field: fill(src, path, field, people=PEOPLE), actor)
    if "pre_bos_minutes" in have:
        out["pre_bos_minutes"] = have["pre_bos_minutes"]
    else:
        lines = [f"Minutes of the Pre-BoS Meeting — {dept['dept_name']}", NOTE,
                 f"Meeting date: {BOS_DATE}. Agenda: the DIAC and DPAC recommendations on the curriculum.",
                 "Members present: as in the DIAC and DPAC compositions.",
                 "Resolved and approved: the recommendations go to the Board of Studies."]
        out["pre_bos_minutes"] = _store(db, dept["dept_code"], year, "pre_bos", "pre_bos_minutes",
                                        "Pre_BoS_Minutes.pdf",
                                        lambda path: path.write_bytes(demo_dept._pdf(lines)), actor)
    return out


# ---------------------------------------------------------------------------
# the entry point
# ---------------------------------------------------------------------------

def pack_for(db, dept):
    """The data pack that belongs to a department, if it has one."""
    from .packs import PACK_DIR
    for path in sorted(PACK_DIR.glob("*.json")):
        pack = get_pack(path.stem)
        found = find_department(db, pack["department"])
        if found and found["dept_code"] == dept["dept_code"]:
            return pack
    return None


def fill_from_drive(dept, year, actor):
    """Fill every stage and programme part of the department. Returns a list of
    what was filled, for the message on the page."""
    db = get_db()
    pack = pack_for(db, dept)
    if not pack:
        raise KeyError(dept["dept_code"])
    load_pack(pack["key"], year, actor)
    code = dept["dept_code"]
    done = []

    def fresh():
        return get_or_create_submission(code, year)

    def submitted(stage):
        return ((fresh().get("stages") or {}).get(stage) or {}).get("status") == "submitted"

    sub = fresh()
    # Department Information: the department's own record and the catalogue
    if not submitted("dept_info"):
        stored = ((sub.get("stages") or {}).get("dept_info") or {}).get("data")
        data = stored or prefill_for("dept_info", dept, year, None, sub)
        data.setdefault("contact", {}).setdefault("office_email", dept.get("office_email") or "csit@jainuniversity.ac.in")
        data["contact"].setdefault("faculty_count", 20)
        save_draft(code, year, "dept_info", data)
        done.append("Department Information")

    # Pre-BoS and BoS Documents
    for stage, key, build in (("pre_bos", "pre_bos_files", _pre_bos_files),
                              ("bos_documents", "bos_files", _bos_files)):
        if submitted(stage):
            continue
        state = (fresh().get("stages") or {}).get(stage) or {}
        data = dict(state.get("data") or {})
        have = {k: v for k, v in (data.get(key) or {}).items()
                if v and (not isinstance(v, list) or v)}
        data[key] = build(db, dept, year, actor, have)
        if stage == "bos_documents":
            data.setdefault("meeting", {})["bos_date"] = (data.get("meeting") or {}).get("bos_date") or BOS_DATE
        save_draft(code, year, stage, data)
        done.append(STAGE_BY_KEY[stage]["title"])

    # every programme, in the order a department fills them
    for programme in programmes_of(fresh(), dept):
        pcode = programme["programme_code"]
        from .workflow import parts_for
        stage_def = next(s for s in STAGE_BY_KEY.values() if s.get("parts"))
        builds = {"prog_curriculum": _curriculum, "prog_syllabus": _syllabus, "prog_revision": _revision}
        for part in parts_for(stage_def):
            build = builds.get(part)
            sub = fresh()
            if _is_submitted(sub, pcode, part):
                continue
            stored = programme_stage_state(sub, pcode, part).get("data") or {}
            if build is None:
                # an earlier batch: the current batch's syllabus as a stand-in
                current = programme_stage_state(sub, pcode, "prog_syllabus").get("data") or {}
                data = _batch_syllabus(current, STAGE_BY_KEY[part].get("batch"), stored)
                base = prefill_for(part, dept, year, programme, fresh())
                for k, v in base.items():
                    data.setdefault(k, v)
                save_draft(code, year, part, data, pcode)
                done.append(f"{pcode} · {STAGE_BY_KEY[part]['title']}")
                continue
            if part == "prog_curriculum":
                syl = (programme_stage_state(sub, pcode, "prog_syllabus").get("data") or {}).get("courses")
                from_syl = (_syllabus(sub, programme, {"courses": syl}, year)["courses"]
                            if syl and not stored.get("semester_structure") else ())
                data = build(dept, programme, sub, year, stored, from_syl)
                if from_syl:                    # the syllabus gets the same codes
                    syl_codes = {"courses": list(from_syl)}
                    save_draft(code, year, "prog_syllabus", {**(programme_stage_state(
                        sub, pcode, "prog_syllabus").get("data") or {}), **syl_codes}, pcode)
            else:
                data = build(sub, programme, stored, year)
            if part == "prog_curriculum":
                # a pack's curriculum carries its own degree; the rest follow it
                from .packs import _with_degree
                programme = _with_degree(programme, data)
            # fields the programme opens with (name, code, department) stay as the form has them
            base = prefill_for(part, dept, year, programme, fresh())
            merged = {k: ({**base[k], **v} if isinstance(v, dict) and isinstance(base.get(k), dict) else v)
                      for k, v in data.items()}
            for k, v in base.items():
                merged.setdefault(k, v)
            save_draft(code, year, part, merged, pcode)
            done.append(f"{pcode} · {STAGE_BY_KEY[part]['title']}")
    db.submissions.update_one({"dept_code": code, "academic_year": year},
                              {"$set": {"autofilled": {"by": actor, "at": now(), "date": date.today().isoformat()}}})
    return done
