"""One made-up department the Office can sign in as and look at from the
admin side: "Department of Demonstration Studies" (code DEMO).

Every stage and every programme part is filled in and saved, with small
PDFs and photos that carry real words — so signing in as it, you only
review and submit, stage by stage, and watch the Office's side react: the
updates feed, the keyword check, the review with its timings. Making it again wipes the old one
first. It is marked `demo: True` everywhere and named so nobody mistakes it.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from .db import get_db, issue_department_login, now
from .schema import STAGE_BY_KEY

CODE = "DEMO"
NAME = "Department of Demonstration Studies"

DEPT = {
    "dept_code": CODE, "dept_name": NAME,
    "faculty": "Faculty of Demonstration", "school": "School of Demonstration",
    "campus": "Jain Global Campus", "place": "Bangalore",
    "hod_name": "Dr. Demo Head", "hod_email": "demo.head@example.edu",
    "hod_phone": "9000000000", "hod_designation": "Head of the Department",
    "active": True, "demo": True,
}

PROGRAMMES = [
    {"programme_code": "DEMOBBA", "programme_name": "BBA in Demonstration Management",
     "degree": "UG", "source": "new", "decision": "keep"},
    {"programme_code": "DEMOBCOM", "programme_name": "B.Com in Demonstration Accounting",
     "degree": "UG", "source": "new", "decision": "keep"},
]

# file name → (stage, field, lines of text inside it); every one the right
# document for its box, so the keyword check passes throughout
DOCS = {
    "vision_mission.pdf": ("bos_documents", "vision_mission", [
        "Department Vision, Mission and Programme Overview",
        "Vision: to be a centre of excellence in management education.",
        "Mission: to develop ethical, skilled and socially responsible professionals.",
        "Programme overview: BBA and B.Com, three years, NEP 2020.",
        "Programme Educational Objectives (PEO) and Programme Specific Outcomes (PSO) attached."]),
    "minutes.pdf": ("bos_documents", "minutes", [
        "Minutes of the Board of Studies Meeting",
        "Department of Demonstration Studies, held on 12 March 2027 at 10:00 am",
        "Members present: Dr. Demo Head, Chairperson; Prof. Leela Iyer, External Member",
        "Agenda item 1: curriculum for the BBA in Demonstration Management",
        "Resolved that the BBA curriculum for 2027-28 be approved.",
        "Approved two new electives in the B.Com programme."]),
    "external_profile.pdf": ("bos_documents", "external_profiles", [
        "Profile: Prof. Leela Iyer", "Designation: Professor of Management, Demo University",
        "Qualification: Ph.D in Management", "Experience: 22 years of teaching and research",
        "Publications: 40 papers in refereed journals"]),
    "attendance.pdf": ("bos_documents", "attendance", [
        "Attendance Sheet — Board of Studies Meeting, 12 March 2027",
        "Sl. No   Name   Designation   Signature",
        "1  Dr. Demo Head  Chairperson  (signed)", "2  Prof. Leela Iyer  External Member  (signed)",
        "Members present: 6"]),
    "feedback.pdf": ("bos_documents", "feedback_curriculum", [
        "Stakeholder Feedback for Curriculum Design and Development",
        "Survey of students, alumni, employers and faculty — 212 responses",
        "Rating scale 1 to 5; average rating 4.2",
        "Feedback: more case studies and analytics in the curriculum."]),
}
PHOTOS = ["meeting_photo_1.jpg", "meeting_photo_2.jpg"]

# who sits on the demo's DIAC and PAC — made up, one per category
PEOPLE = {
    "Dean of Faculty / Director of School": ("Dr. Meera Kulkarni", "Dean, Faculty of Demonstration"),
    "Head of Department": ("Dr. Demo Head", "Professor and Head"),
    "Area Chair / Area Head": ("Dr. Arun Nair", "Area Chair, Finance"),
    "Program Head / Program Co-Ordinator": ("Prof. Leela Iyer", "Programme Head, BBA"),
    "Faculty Placement Coordinators": ("Ms. Divya Rao", "Placement Coordinator"),
    "Industry Experts": ("Ms. Asha Rao", "Director, Demo Industries Ltd"),
    "Industry Expert": ("Ms. Asha Rao", "Director, Demo Industries Ltd"),
    "Alumni": ("Mr. Vikram Das", "Analyst, Demo Bank (BBA 2019)"),
    "Senior Non-Teaching Staff": ("Mr. Ravi Kumar", "Academic Administrator"),
    "Representative of the Office of Academics": ("Dr. Sunita Menon", "Deputy Director, OOA"),
    "Current Student": ("Ms. Priya Menon", "BBA, Semester 5"),
    "Professor": ("Prof. Karthik Bhat", "Professor"),
    "Associate Professor": ("Dr. Neha Shetty", "Associate Professor"),
    "Assistant Professor": ("Mr. Rahul Joshi", "Assistant Professor"),
    "Parent": ("Mr. Suresh Gowda", "Parent of a BBA student"),
    "Academician": ("Prof. R. Srinivasan", "Professor (retd.), 30 years in management education"),
}

def _pdf(lines):
    """A one-page PDF with these lines in Helvetica — enough for the text
    layer to be read, with no library needed to make it."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    y, ops = 780, ["BT", "/F1 11 Tf"]
    for i, line in enumerate(lines):
        size = 14 if i == 0 else 11
        ops.append(f"/F1 {size} Tf 1 0 0 1 60 {y} Tm ({esc(line)}) Tj")
        y -= 24 if i == 0 else 18
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def remove(db=None):
    db = get_db() if db is None else db
    user = db.users.find_one({"dept_code": CODE, "role": "department"})
    for col in ("submissions", "files", "notifications"):
        db[col].delete_many({"dept_code": CODE})
    db.users.delete_many({"dept_code": CODE, "role": "department"})
    db.departments.delete_many({"dept_code": CODE})
    return user


def _photo(path, n):
    """A small picture standing in for a geotagged meeting photo."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (640, 420), (14, 61, 124) if n == 1 else (31, 107, 68))
        d = ImageDraw.Draw(img)
        d.rectangle([20, 20, 620, 400], outline=(242, 169, 0), width=6)
        d.text((40, 40), f"BoS meeting photo {n}", fill=(255, 255, 255))
        d.text((40, 70), "Department of Demonstration Studies · 12 Mar 2027", fill=(255, 255, 255))
        d.text((40, 360), "12.9716 N, 77.5946 E", fill=(255, 255, 255))
        img.save(path, "JPEG", quality=80)
    except Exception:              # no imaging library: a 1×1 picture will do
        path.write_bytes(bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9"))


# ---------------------------------------------------------------------------
# a full, valid record for every stage — what the demo login opens to
# ---------------------------------------------------------------------------

# a three-year UG programme that meets UGC Table 2: (group, credits, L, E, how many)
_PLAN = [
    ("Major (Core)", 4, 4, 0, 17),
    ("Minor Stream", 4, 4, 0, 6),
    ("Multidisciplinary", 3, 3, 0, 3),
    ("Ability Enhancement Courses (AEC)", 2, 2, 0, 4),
    ("Skill Enhancement Courses (SEC)", 3, 3, 0, 3),
    ("Value Added Courses (VAC)", 2, 2, 0, 4),
    ("Summer Internship", 2, 0, 4, 1),
]
_TOPICS = {
    "Major (Core)": ["Principles of Management", "Financial Accounting", "Business Economics",
                     "Organisational Behaviour", "Marketing Management", "Cost Accounting",
                     "Human Resource Management", "Business Statistics", "Corporate Finance",
                     "Business Law", "Operations Management", "Management Accounting",
                     "Business Research Methods", "Strategic Management", "International Business",
                     "Entrepreneurship", "Business Analytics"],
    "Minor Stream": ["Digital Marketing", "Consumer Behaviour", "Retail Management",
                     "Services Marketing", "Brand Management", "Sales Management"],
    "Multidisciplinary": ["Environmental Studies", "Indian Economy", "Psychology at Work"],
    "Ability Enhancement Courses (AEC)": ["English Communication I", "English Communication II",
                                          "Business Communication", "Kannada / Hindi"],
    "Skill Enhancement Courses (SEC)": ["Spreadsheet Skills", "Data Visualisation", "Tally and GST"],
    "Value Added Courses (VAC)": ["Indian Constitution", "Yoga and Wellbeing", "Professional Ethics",
                                  "Design Thinking"],
    "Summer Internship": ["Summer Internship"],
}


def _courses(prefix):
    rows, per_sem, n = [], {}, 0
    for group, credits, l, e, count in _PLAN:
        for i in range(count):
            n += 1
            sem = 6 if group == "Summer Internship" else (n - 1) % 6 + 1
            per_sem[sem] = per_sem.get(sem, 0) + 1
            rows.append({"semester": sem, "track": "All semesters", "nep_category": group,
                         "course_code": f"27{prefix}{sem}C{per_sem[sem]:02d}",
                         "course_title": _TOPICS[group][i % len(_TOPICS[group])],
                         "l": l, "t": 0, "p": 0, "e": e, "credits": credits,
                         "cia": 50, "ese": 50, "total_marks": 100})
    rows.sort(key=lambda r: (r["semester"], r["course_code"]))
    return rows


def _modules(title, previous=False):
    out = []
    for m, (name, hrs) in enumerate([("Foundations", 12), ("Concepts and frameworks", 12),
                                      ("Tools and techniques", 12), ("Applications", 12),
                                      ("Contemporary issues", 12)], 1):
        now_text = f"{name} ({hrs} Hrs) — {title}: {name.lower()}, with cases from Indian business."
        if previous:
            out.append({"previous": f"{name} ({hrs} Hrs) — {title}: {name.lower()}.",
                        "revised": now_text, "pct": 30 if m % 2 else 10})
        else:
            out.append({"previous": "", "revised": now_text, "pct": None})
    return out


def _syllabus_row(c, batch_year, previous=False):
    hours = c["credits"] if c["credits"] else 2
    return {"course_code": c["course_code"], "course_title": c["course_title"],
            "semester": c["semester"], "credits": c["credits"], "hours_per_week": hours,
            "teaching_hours": hours * 15, "year_latest": batch_year,
            "pedagogy": "Lectures, case studies, group discussion and a field visit.",
            "outcomes": f"Explain the key ideas of {c['course_title']}\n"
                        f"Apply them to business problems\nAnalyse a real case and present findings",
            "modules": _modules(c["course_title"], previous),
            "skill_activities": "A short project with a local business, presented in class.",
            "books": "Kotler, P. Principles (latest edition)\nRobbins, S. Management (latest edition)"}


def sample(stage_key, programme=None, files=None, year="2027-28"):
    """Sample answers for one stage or programme part, valid as they stand."""
    files = files or {}
    if stage_key == "dept_info":
        return {"identity": {"dept_name": NAME, "faculty": DEPT["faculty"], "school": DEPT["school"],
                             "campus": DEPT["campus"], "academic_year": year},
                "contact": {"office_email": "demo.office@example.edu", "faculty_count": 18},
                "programmes_offered": PROGRAMMES}
    if stage_key == "pre_bos":
        return {"pre_bos_files": {k: files[k] for k in ("diac_signed", "dpac_signed") if k in files}}
    if stage_key == "bos_documents":
        box = {k: files[k] for k in ("bos_composition", "vision_mission", "minutes", "attendance")
               if k in files}
        for k in ("external_profiles", "geotagged_photos", "feedback_curriculum"):
            if k in files:
                box[k] = files[k] if isinstance(files[k], list) else [files[k]]
        return {"meeting": {"bos_date": "2027-03-12"}, "bos_files": box}
    if not programme:
        return {}
    code = programme["programme_code"]
    prefix = "BBA" if "BBA" in code else "BCM"
    courses = _courses(prefix)
    if stage_key == "prog_curriculum":
        return {
            "details": {"degree_level": "UG - 3 Year", "specialisation": "General"},
            "profile": {
                "objective": f"To give students of the {programme['programme_name']} a sound grounding "
                             "in business knowledge and skills.\nTo prepare them for careers in industry, "
                             "for entrepreneurship and for higher study.\nTo build ethical values and "
                             "social responsibility.",
                "duration_months": 36, "intake": 120,
                "eligibility": "A pass in 10+2 or equivalent from a recognised board, with at least "
                               "45% marks in aggregate (40% for reserved categories).",
                "course_specialisation": programme["programme_name"],
            },
            "semester_structure": courses,
        }
    batch = (STAGE_BY_KEY.get(stage_key) or {}).get("batch") or ""
    if stage_key == "prog_syllabus" or stage_key.startswith("prog_syllabus_b"):
        y = batch[:4] if batch and batch[:4].isdigit() else year[:4]
        return {"courses": [_syllabus_row(c, y) for c in courses]}
    if stage_key == "prog_revision":
        rows = []
        for c in courses:
            mods = _modules(c["course_title"], previous=True)
            rows.append({"course_code": c["course_code"], "course_title": c["course_title"],
                         "semester": c["semester"], "year_previous": "2024", "year_latest": "2027",
                         "prev_code": c["course_code"].replace("27", "24", 1),
                         "prev_title": c["course_title"], "modules": mods,
                         "avg_change": round(sum(m["pct"] for m in mods) / len(mods), 1)})
        return {"courses": rows}
    return {}


def _store(db, upload_root, year, username, stage, field, name, data, t):
    from .keyword_match import check
    from .summarise import field_label
    folder = upload_root / year / CODE / stage
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}-{name}"
    path = folder / stored
    if callable(data):
        data(path)
    else:
        path.write_bytes(data)
    match = check(path, field, field_label(stage, field))
    db.files.insert_one({"dept_code": CODE, "academic_year": year, "stage": stage,
                         "field": field, "original_name": name, "stored_name": stored,
                         "size": path.stat().st_size, "uploaded_by": username,
                         "uploaded_at": t, "keyword_match": match, "demo": True})
    val = {"name": name, "stored": stored, "size": path.stat().st_size,
           "url": f"/department/file/{stage}/{stored}", "match": match}
    if name.lower().endswith(".pdf"):
        val["thumb"] = val["url"] + "?thumb=1"
    return val


USERNAME = "demo.dept"


def _files_for(db, year):
    """The demo's uploaded files, as the form stores them."""
    files = {}
    for r in db.files.find({"dept_code": CODE, "academic_year": year}).sort("uploaded_at", 1):
        v = {"name": r["original_name"], "stored": r["stored_name"], "size": r.get("size"),
             "url": f"/department/file/{r['stage']}/{r['stored_name']}", "match": r.get("keyword_match")}
        if r["original_name"].lower().endswith(".pdf"):
            v["thumb"] = v["url"] + "?thumb=1"
        if r["field"] in ("geotagged_photos", "external_profiles", "feedback_curriculum"):
            files.setdefault(r["field"], []).append(v)
        else:
            files[r["field"]] = v
    return files


def create(year, upload_root, actor="system"):
    """Make (or remake) the demo department: its login (username demo.dept),
    and its sample documents uploaded — the forms themselves start empty.
    Signed in as it, one press of “Fill everything” fills every stage.
    Returns (username, password)."""
    db = get_db()
    remove(db)
    t = now()
    taken = db.users.find_one({"username": USERNAME})
    db.departments.insert_one({**DEPT, "created_at": t, "updated_at": t,
                               **({} if taken else {"username": USERNAME})})
    dept = db.departments.find_one({"dept_code": CODE})
    username, password = issue_department_login(db, dept, actor=actor)

    for name, (stage, field, lines) in DOCS.items():
        _store(db, upload_root, year, username, stage, field, name, _pdf(lines), t)
    # the signed composition forms: the university's own templates, filled in
    from pathlib import Path
    from .template_check import TEMPLATES, fill
    static = Path(__file__).resolve().parent / "static"
    for field, name in (("diac_signed", "Composition_of_DIAC_signed.docx"),
                        ("dpac_signed", "Composition_of_PAC_signed.docx")):
        src = static / TEMPLATES[field]["file"]
        _store(db, upload_root, year, username, "pre_bos", field, name,
               (lambda path, src=src, field=field: fill(src, path, field, people=PEOPLE)), t)
    from .template_check import make_bos_composition
    _store(db, upload_root, year, username, "bos_documents", "bos_composition",
           "Composition_of_BoS_Members.docx", (lambda path: make_bos_composition(path, PEOPLE)), t)
    for i, n in enumerate(PHOTOS, 1):
        _store(db, upload_root, year, username, "bos_documents", "geotagged_photos", n,
               (lambda path, i=i: _photo(path, i)), t)
    return username, password


def fill_all(year):
    """Every stage and every programme part filled with valid sample answers
    and saved as a draft — ready to review and submit, in order. Stages
    already submitted are left alone. Returns how many were filled."""
    from .schema import PARTS, STAGE_KEYS
    from .workflow import batches, get_or_create_submission, save_draft

    db = get_db()
    files = _files_for(db, year)
    sub = get_or_create_submission(CODE, year)
    done = 0
    for key in STAGE_KEYS:
        if (STAGE_BY_KEY.get(key) or {}).get("parts"):
            continue
        if ((sub.get("stages") or {}).get(key) or {}).get("status") == "submitted":
            continue
        save_draft(CODE, year, key, sample(key, files=files, year=year))
        done += 1
    part_keys = [p["key"] for p in PARTS] + [b["key"] for b in batches().get("existing", [])]
    for prog in PROGRAMMES:
        code = prog["programme_code"]
        for key in part_keys:
            if key not in STAGE_BY_KEY:
                continue
            if (((sub.get("programmes") or {}).get(code) or {}).get(key) or {}).get("status") == "submitted":
                continue
            save_draft(CODE, year, key, sample(key, prog, files, year), code)
            done += 1
    return done
