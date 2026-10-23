"""
Declarative field schema for the OOA Data Portal.

Every Word/Excel template in the "BOS DATA REPOSITORY" sheet is expressed here as
typed fields instead of a document to download, fill offline and re-upload.
The renderer (app/static/js/stage.js) and the server-side validator
(app/validation.py) both read this single source of truth.

FIELD TYPES
    text | textarea | integer | number | email | phone | date | select |
    multiselect | checkbox | file | readonly

SECTION TYPES
    fields  -> a flat block of fields
    table   -> a repeating grid; `columns` are field definitions, rows are
               added/removed by the user
"""
import re

# --------------------------------------------------------------------------
# Shared option lists
# --------------------------------------------------------------------------

# The campus list lives in the configuration, where the admin screens read it
# from too; a second copy here would drift the moment a campus is added.
from config import Config as _Config  # noqa: E402

CAMPUSES = list(_Config.CAMPUSES)

DEGREE_LEVELS = [
    "UG - 3 Year",
    "UG - 4 Year (Honours)",
    "UG - 4 Year (Honours with Research)",
    "PG - 1 Year",
    "PG - 2 Year",
    "PG Diploma - 1 Year",
]

# every course in the programme structure is marked out of this
MARKS_TOTAL = 100

# the semesters a course can sit in — picked from a list, never typed
SEMESTERS = list(range(1, 9))

NEP_CATEGORIES = [
    "Major (Core)",
    "Minor Stream",
    "Multidisciplinary",
    "Ability Enhancement Courses (AEC)",
    "Skill Enhancement Courses (SEC)",
    "Value Added Courses (VAC)",
    "Summer Internship",
    "Research Project / Dissertation",
]

# Bloom's Taxonomy: the level a course outcome reaches (1-6), and the verbs a
# CO usually opens with at each level — a suggestion; the department chooses
BLOOM_LEVELS = ["Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"]
BLOOM_VERB_LEVEL = {v: n for n, verbs in enumerate((
    "remember recall define list identify name state recognise recognize label match memorise memorize "
    "record repeat",
    "understand explain describe discuss summarise summarize interpret classify paraphrase infer outline "
    "translate express report review",
    "apply use demonstrate solve prepare compute calculate implement execute illustrate operate employ "
    "perform determine practise practice show",
    "analyse analyze examine compare contrast differentiate distinguish reconcile investigate categorise "
    "categorize organise organize attribute deconstruct",
    "evaluate assess critique justify judge appraise defend argue recommend prioritise prioritize verify "
    "validate",
    "create design develop formulate construct compose plan produce generate propose devise build invent "
    "integrate",
), start=1) for v in verbs.split()}


def bloom_level(text):
    """The level a course outcome's opening verb usually stands for, or None."""
    words = str(text or "").strip().split()
    return BLOOM_VERB_LEVEL.get(words[0].lower().strip(".,:;")) if words else None


# the columns of every course's CO-PO-PSO Mapping, as the sample syllabus has them
OUTCOME_COLUMNS = [f"PO{n}" for n in range(1, 10)] + [f"PSO{n}" for n in range(1, 5)]


def objective_lines(text):
    """The programme's Objective, one per line, without the numbering it was
    typed with — each course's Course Objectives starts from it."""
    lines = (re.sub(r"^\s*(\d+|[a-zA-Z]|[ivxIVX]+)[.)]\s+|^\s*[-•*]\s*", "", x).strip()
             for x in str(text or "").splitlines())
    return [x for x in lines if x]


def course_info(r):
    """A course's Course Information, from its line of the Curriculum table:
    semester, credits, L-T-P-E, contact hours (15 for every credit) and
    CA : ESE — so the syllabus never asks for them again."""
    def num(k):
        try:
            v = float(str(r.get(k)).strip())
        except (TypeError, ValueError):
            return None
        return int(v) if v == int(v) else v
    out = {}
    if r.get("semester") not in (None, ""):
        out["semester"] = r["semester"]
    hours = [num(k) for k in ("l", "t", "p", "e")]
    if all(h is not None for h in hours):
        out["ltpe"] = "-".join(str(h) for h in hours)
        out["hours_per_week"] = sum(hours)
    credits = num("credits")
    if credits is not None:
        out["credits"] = credits
        out["teaching_hours"] = int(round(credits * 15))
    cia, ese = num("cia"), num("ese")
    if cia is not None and ese is not None:
        out["ca_ese"] = f"{cia}:{ese}"
    return out


# what each is called in the Course category list: the credit table's own headings
CATEGORY_LABELS = {
    "Major (Core)": "Major",
    "Minor Stream": "Minor",
    "Multidisciplinary": "Multi-Disciplinary / OE",
    "Ability Enhancement Courses (AEC)": "Ability Enhancement / AEC",
    "Skill Enhancement Courses (SEC)": "Skill Enhancement / SEC",
    "Value Added Courses (VAC)": "Common Value Added / VAC",
    "Summer Internship": "Summer Internship / INTERNSHIP",
    "Research Project / Dissertation": "Research Project / Dissertation / PROJECT",
}

# what an older draft (or a pack) called a course group, read as the category it stands for
_OLDER_GROUPS = {
    "Discipline Specific Elective (DSE)": "Major (Core)",
    "Mandatory Non-Credit Course": "Major (Core)",
    "Mandatory Non-Credit Audit Course": "Major (Core)",
    "Generic Core": "Major (Core)",
    "Specialisation Core": "Major (Core)",
    "Generic Elective": "Major (Core)",
    "Specialisation Elective": "Major (Core)",
    "Open Elective": "Multidisciplinary",
    "Research / Thesis / Project / Patent": "Research Project / Dissertation",
}


def course_category(value, credits=None, title=""):
    """A course group as one of the course categories: a group already one of
    them stays; any other word (an older draft's, a pack's own) becomes the
    category it stands for. A course with no credits is counted as non-credit
    by its zero, whichever category it sits in."""
    v = str(value or "").strip()
    if v in NEP_CATEGORIES:
        return v
    if v in _OLDER_GROUPS:
        return _OLDER_GROUPS[v]
    # the group's own words decide; a course's title only when it has no group
    low = (v or str(title or "")).lower()
    if any(w in low for w in ("research", "thesis", "dissertation", "project", "patent")):
        return "Research Project / Dissertation"
    if "internship" in low:
        return "Summer Internship"
    if not v:
        return ""
    if "minor" in low:
        return "Minor Stream"
    if "open" in low or "multi" in low:
        return "Multidisciplinary"
    if "skill" in low:
        return "Skill Enhancement Courses (SEC)"
    if "ability" in low or "language" in low:
        return "Ability Enhancement Courses (AEC)"
    if "value" in low:
        return "Value Added Courses (VAC)"
    return "Major (Core)"


# course groups that carry no credits; counted in their own columns
NON_CREDIT_GROUPS = ["Mandatory Non-Credit Course", "Mandatory Non-Credit Audit Course"]

COURSE_TYPES = ["Theory", "Practical", "Theory + Practical", "Project", "Internship", "Seminar"]

FEEDBACK_SOURCES = ["Faculty", "Student", "Alumni", "Employer", "Industry", "Parent", "Academic Peer"]

APPROVAL_LEVELS = [
    "Head of the Department",
    "Dean / Director",
    "Office of Academics Verification",
    "Academic Council",
    "Board of Management",
]


# --------------------------------------------------------------------------
# Stage 1 — Department Information
# --------------------------------------------------------------------------

DEPARTMENT_INFORMATION = {
    "key": "dept_info",
    "group": "Level 0 · Department",
    "title": "Department Information",
    "blurb": "",
    "sections": [
        {
            "key": "identity",
            "title": "Department identity",
            "type": "fields",
            "display": "cards",
            # copied from the Office of Academics record on every open; the
            # department cannot change it — the Office corrects the record
            "frozen": True,
            "fields": [
                {"name": "dept_name", "label": "Department name", "type": "text", "required": True,
                 "prefill": "dept_name", "help": "Exactly as it appears on official university records."},
                {"name": "faculty", "label": "Faculty", "type": "text", "prefill": "faculty"},
                {"name": "school", "label": "School", "type": "text", "required": True,
                 "prefill": "school"},
                {"name": "campus", "label": "Campus", "type": "select", "required": True,
                 "options": CAMPUSES, "prefill": "campus"},
                {"name": "academic_year", "label": "Academic year", "type": "readonly", "prefill": "academic_year"},
            ],
        },
        {
            "key": "programmes_offered",
            "title": "Programmes offered",
            "help": "Tick the programmes you run this year — one is enough. Add a new programme at the end.",
            "type": "programme_list",
            "degrees": ["UG", "PG", "PG-1Yr", "PGD"],
            # the tabs the list is split into, by the workbook's Degree column
            "tabs": [{"key": "UG", "label": "UG programmes", "degrees": ["UG"]},
                     {"key": "PG", "label": "PG programmes",
                      "degrees": ["PG", "PG-1Yr", "PGD"]}],
            "rules": ["programmes_offered_valid"],
            # what the Excel and Word exports print for each programme
            "columns": [
                {"name": "programme_code", "label": "Code"},
                {"name": "programme_name", "label": "Programme"},
                {"name": "degree", "label": "Degree"},
                {"name": "source", "label": "From"},
                {"name": "decision", "label": "Offered / not offered"},
            ],
        },
    ],
}



# --------------------------------------------------------------------------
# Curriculum Matrix wording
# --------------------------------------------------------------------------

NEP_FRAMEWORKS = ["NEP 2020", "CBCS", "Outcome Based Education", "Other"]

TRACKS = ["All semesters", "Honours", "Honours with Research"]

# the university-wide wording from the sample curriculum
DEFAULT_REGULATIONS = {
    "reservation_policy": "Reservation Policy as prescribed by Central Government and UGC "
                          "Guidelines",
    "selection_procedure": "Jain Entrance Test (JET) / Personal Interview. The selection "
                           "procedure for the Multiple Entry would be as per the University's "
                           "Lateral Entry Rules.",
    "medium": "English",
    "pattern": "Semester Model",
    "assessment": "The courses will have 50% Continuous Assessment and 50% Term End "
                  "(University) examination. However, some courses (not more than 10% of the "
                  "total programme credits) may have 100% Continuous Assessment.",
    "passing": "The assessment of the student for each examination is done based on relevant "
               "performance. Maximum Grade Point (GP) is 10 corresponding to O (Outstanding). "
               "For all courses, a student is required to secure a minimum of 35% marks "
               "separately in ESE and 40% in aggregate in a course to secure a pass grade. "
               "(The Percentage Weightage of CA to ESE is 50:50 for theory courses.) A “R” "
               "(Reappear) Grade will be awarded for unsatisfactory performance, i.e. if the "
               "score is less than 40% aggregate.",
    "award": "Under Graduate Certificate will be awarded at the end of semester 2, subject to "
             "a minimum 4.00 CGPA and the successful completion of the 04-credit Vocational "
             "Course in the summer (NCrF Level 4.5).\n"
             "Under Graduate Diploma will be awarded at the end of semester 4, subject to a "
             "minimum 4.00 CGPA and the successful completion of the 04-credit Vocational "
             "Course in the summer (NCrF Level 5).\n"
             "The Bachelor's degree will be awarded at the end of semester 6, and the "
             "Honours / Honours with Research degree at the end of semester 8.",
}



# the PG Course Matrix's own wording where it differs from the UG template
PG_REGULATIONS = {
    "selection_procedure": "Jain Entrance Test (JET) / Personal Interview.",
    "pattern": "Semester",
    "assessment": "The courses will have 60% Continuous Assessment and 40% Term End (University) "
                  "examination. However, some courses (not more than 10% of the total programme "
                  "credits) may have 100% Continuous Assessment.",
    "passing": "The assessment of the student for each examination is done based on performance. "
               "Maximum Grade Point (GP) is 10 corresponding to O (Outstanding). For all courses, a "
               "student is required to pass both Continuous Assessment and Term End examinations "
               "separately with a minimum Grade Point corresponding to Grade P. Students securing "
               "less than the minimum marks in any head of passing will be declared FAIL. The "
               "University awards the degree to the student who has achieved the minimum CGPA, out "
               "of a maximum of 10 CGPA, for the Programme.",
    "award": "The Master's degree will be awarded at the end of the final semester examination, "
             "taking into consideration the performance in all semester examinations, after "
             "obtaining a minimum of 4.00 CGPA out of 10 CGPA.",
    "fee": "As notified by the University for the academic year — Academic fee p.a., Institute "
           "deposit and Total, for Indian students (in INR), and for NRI / PIO / OCI and foreign "
           "nationals (in US$).",
}


# --------------------------------------------------------------------------
# Stage 1 — Pre-BoS  (DIAC and DPAC only)
# --------------------------------------------------------------------------

PRE_BOS = {
    "key": "pre_bos",
    "group": "Stage 1 · Pre-BoS",
    "title": "Pre-BoS",
    "blurb": "Upload the signed DIAC and DPAC composition documents.",
    "source_templates": [
        "[Template] Composition of DIAC.docx",
        "[Template] Composition of the Program Assessment Committee Template.docx",
    ],
    "sections": [
        {
            "key": "pre_bos_files",
            "title": "Signed composition documents",
            "help": "Please fill in and upload the DIAC, DPAC, and Pre-BoS templates in the respective sections.",
            "type": "fields",
            "fields": [
                {"name": "diac_signed",
                 "label": "Composition of the Department Industry-Academia Cell (DIAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "template": "templates/Composition_of_DIAC.docx",
                 "help": "Fill a name and designation for every category in the template. A Word "
                         "file is checked row by row; anything left blank is listed."},
                {"name": "dpac_signed",
                 "label": "Composition of the Department Programme Assessment Committee (DPAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "template": "templates/Composition_of_PAC.docx",
                 "help": "Fill a name and designation for every category in the template. A Word "
                         "file is checked row by row; anything left blank is listed."},
                {"name": "pre_bos_minutes", "label": "Minutes of the Meeting (Pre-BoS)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "template": "templates/Minutes_of_Pre-BoS_Meeting.docx",
                 "help": "The minutes of the Pre-BoS meeting, signed — PDF or Word."},
                {"name": "notes", "label": "Note to the Office of Academic Affairs", "type": "textarea",
                 "rows": 2, "wide": True, "help": "Optional."},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 2 — BoS Documents  (upload folder)
# --------------------------------------------------------------------------

BOS_DOCUMENTS = {
    "key": "bos_documents",
    "group": "Stage 2 · BoS Documents",
    "title": "BoS Documents",
    "blurb": "",
    "sections": [
        {
            "key": "meeting",
            "title": "BoS meeting",
            "type": "fields",
            "fields": [
                {"name": "bos_date", "label": "Date of the BoS meeting", "type": "date", "required": True,
                 "help": "Filled into every Course Revision Log automatically."},
            ],
        },
        {
            "key": "bos_files",
            "title": "BoS documents",
            # one row per document, opened with a click to upload
            "display": "accordion",
            "help": "Kindly select and upload the relevant document.",
            "type": "fields",
            "fields": [
                {"name": "bos_composition", "label": "Composition of BoS Members", "type": "file", "template": "templates/Composition_of_BoS_Members.docx",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "help": "The table of categories, roles and members. A Word file is checked row by "
                         "row; any category with no member is listed."},
                {"name": "external_profiles", "label": "Profiles of External Experts", "type": "file", "template": "templates/Profile_of_External_Expert.docx",
                 "required": True, "wide": True, "multiple": True, "accept": ".pdf,.docx,.doc,.zip",
                 "help": "One file per expert, or all of them at once."},
                {"name": "minutes", "label": "Minutes of Meeting (MoM)", "type": "file", "template": "templates/Minutes_of_BoS_Meeting.docx",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "geotagged_photos", "label": "Geotagged photos of the meeting", "type": "file",
                 "required": True, "wide": True, "multiple": True,
                 "accept": ".jpg,.jpeg,.png,.pdf,.zip"},
                {"name": "attendance", "label": "Scanned Attendance Sheet", "type": "file", "template": "templates/Attendance_Sheet_BoS.docx",
                 "required": True, "wide": True, "accept": ".pdf,.jpg,.jpeg,.png"},
                {"name": "vision_mission",
                 "label": "Department Vision, Mission, PEOs and POs", "type": "file", "template": "templates/Vision_Mission_PEOs_POs.docx",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "feedback_curriculum",
                 "label": "Stakeholder Feedback (For Curriculum Design and Development)",
                 "type": "file", "template": "templates/Stakeholder_Feedback_Curriculum.docx", "required": True, "wide": True, "multiple": True,
                 "accept": ".pdf,.docx,.xlsx",
                 "help": "The responses or the e-mails from industry experts, alumni, employers "
                         "and others reviewing the curriculum."},
                {"name": "feedback_new_programme", "label": "Stakeholder Feedback (New Programme)",
                 "type": "file", "template": "templates/Stakeholder_Feedback_New_Programme.docx", "wide": True, "multiple": True, "accept": ".pdf,.docx,.xlsx",
                 "help": "Only if the department is proposing a new programme."},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 3 — Curriculum: per programme, Curriculum · Syllabus · Course Revision
# --------------------------------------------------------------------------

PROGRAMME_CURRICULUM = {
    "key": "prog_curriculum",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Curriculum",
    "blurb": "",
    "per_programme": True,
    "sections": [
        {
            "key": "details",
            "title": "Programme details",
            "type": "fields",
            "fields": [
                # code and name come from Department Information and head the
                # page already — kept for the record, not shown or asked again
                {"name": "programme_code", "label": "Programme code", "type": "readonly",
                 "prefill": "programme_code", "hidden": True},
                {"name": "programme_name", "label": "Programme", "type": "readonly",
                 "prefill": "programme_name", "wide": True, "hidden": True},
                {"name": "degree_level", "label": "Degree / Duration", "type": "select",
                 "required": True, "options": DEGREE_LEVELS, "prefill": "degree_level",
                 "reload_on_change": True},
                {"name": "specialisation", "label": "Specialisation", "type": "text"},
                # worked out, never typed: the current batch's first year to the
                # year the programme ends (2026-29 for a 3-year UG)
                {"name": "batch", "label": "Batch", "type": "readonly", "prefill": "batch_auto",
                 "help": "From the current batch and the degree's duration."},
            ],
        },
        {
            "key": "profile",
            "title": "Regulations — programme profile",
            "help": "Please provide the relevant details for all 12 sections as requested.",
            "type": "fields",
            "fields": [
                {"name": "objective", "label": "1. Objective", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 2, "wide": True,
                 "help": "Please provide 2–6 learning objectives, aligned with Bloom’s Taxonomy."},
                {"name": "duration_months", "label": "2. Duration (in months)", "type": "integer",
                 "required": True, "min": 6, "max": 72},
                {"name": "intake", "label": "3. Student Intake", "type": "integer", "required": True,
                 "min": 1, "max": 2000},
                {"name": "reservation_policy", "label": "4. Reservation", "type": "fixed", "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["reservation_policy"],
                 "fixed_table": [
                     {"head": "I. Within the sanctioned Student Intake",
                      "items": ["a) SC (In Percentage)", "b) ST (In Percentage)",
                                "c) Differently abled (In Percentage)",
                                "d) Defence (In Percentage)"],
                      "note": DEFAULT_REGULATIONS["reservation_policy"]},
                     {"head": "II. Over and above the sanctioned Student Intake",
                      "items": ["a) Kashmiri Migrants (In Seats)",
                                "International Students (In Percentage)"],
                      "note": DEFAULT_REGULATIONS["reservation_policy"]},
                 ],
                 "help": "Fixed by the university; nothing to fill in."},
                {"name": "eligibility", "label": "5. Eligibility", "type": "textarea",
                 "required": True, "rows": 3, "wide": True,
                 "placeholder": "For example: A student who has passed Level 4 / Class 12 "
                                "schooling or its equivalent shall be eligible …"},
                {"name": "selection_procedure", "label": "6. Selection procedure", "type": "textarea",
                 "required": True, "rows": 2, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["selection_procedure"]},
                {"name": "medium", "label": "7. Medium of instruction", "type": "text",
                 "required": True, "prefill_text": DEFAULT_REGULATIONS["medium"]},
                {"name": "pattern", "label": "8. Programme pattern", "type": "text",
                 "required": True, "prefill_text": DEFAULT_REGULATIONS["pattern"]},
                {"name": "course_specialisation", "label": "9. Course & specialisation",
                 "type": "text", "required": True, "wide": True,
                 "derive_from": ["details.programme_name", "details.specialisation"],
                 "placeholder": "For example: BCom (Corporate Finance) Honours / Honours with "
                                "Research — minors as per Annexure I"},
                {"name": "assessment", "label": "10. Assessment", "type": "textarea",
                 "required": True, "rows": 3, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["assessment"]},
                {"name": "passing", "label": "11. Standard of passing", "type": "textarea",
                 "required": True, "rows": 5, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["passing"]},
                {"name": "award", "label": "12. Award of degree / diploma / certificate",
                 "type": "textarea", "required": True, "rows": 5, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["award"]},
            ],
        },
        {
            "key": "credit_classification",
            "title": "Classification of Credits and Number of Non-Credit Courses",
            "help": "The Credit table will be automatically populated based on the courses added to the programme structure below.",
            "type": "credit_distribution",
            "show": "classification",
        },
        {
            "key": "semester_structure",
            "title": "Programme structure — semester scheme",
            "help": "Enter one course per row. Semesters 1 – 6 make the 3-year degree; semesters 7 and 8 under Honours and under Honours with Research are optional — fill them only if the programme offers them.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 8, "choices": SEMESTERS, "width": "64px"},
                {"name": "nep_category", "label": "Course category", "type": "select", "required": True,
                 "options": NEP_CATEGORIES, "option_labels": CATEGORY_LABELS},
                {"name": "course_code", "label": "Course code", "type": "text",
                 "pattern": "^[A-Za-z0-9][A-Za-z0-9 /\\-.]{1,60}$", "width": "110px",
                 "help": "For example 26BCC1C01."},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "l", "label": "L", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "56px", "help": "Lecture hours"},
                {"name": "t", "label": "T", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "56px", "help": "Tutorial hours"},
                {"name": "p", "label": "P", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "56px", "help": "Practical hours"},
                {"name": "e", "label": "E", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "56px", "help": "Experiential hours"},
                {"name": "credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 0, "max": 20, "width": "76px"},
                # every course is out of 100: type one of the two marks and the
                # other is 100 minus it (75 → 25, 35 → 65)
                {"name": "cia", "label": "Continuous Assessment marks", "short": "CA marks", "type": "integer",
                 "required": True, "min": 0, "max": MARKS_TOTAL, "complement": "ese"},
                {"name": "ese", "label": "Term End Examination marks", "short": "TEE marks", "type": "integer",
                 "required": True, "min": 0, "max": MARKS_TOTAL, "complement": "cia"},
                {"name": "total_marks", "label": "Total marks", "type": "integer", "required": True,
                 "min": MARKS_TOTAL, "max": MARKS_TOTAL, "fixed_value": MARKS_TOTAL},
                {"name": "syllabus", "label": "Syllabus", "type": "syllabus_link",
                 "help": "Yes: this course has a syllabus — the link opens it in the current batch. No: it has none. "
                         "Always Yes in semesters 1 and 2."},
                {"name": "revision", "label": "Revision", "type": "revision_link",
                 "help": "Yes: this course is revised in this BoS — the link opens it in Course Revision. No: it is not. "
                         "Always Yes in semesters 1 and 2."},
            ],
            "rules": [
                "ltpe_credit_arithmetic",
                "marks_add_up",
                "semester_within_duration",
                "unique_course_codes",
                "first_year_has_syllabus_and_revision",
            ],
        },
        {
            "key": "credit_distribution",
            "title": "Summary",
            "help": "Worked out from the programme structure, checked against UGC Table 2.",
            "type": "credit_distribution",
            "show": "summary",
            "rules": ["ugc_table2_minimums", "ugc_total_credits"],
        },
        {
            "key": "minors",
            "title": "Minor / Honours — Annexure I",
            "help": "One minor course per row.",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "minor_title", "label": "Minor stream", "type": "text", "required": True,
                 "help": "For example: Analytics"},
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 8, "choices": SEMESTERS, "width": "84px"},
                {"name": "course_code", "label": "Course code", "type": "text", "width": "130px"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 0, "max": 20, "width": "76px"},
            ],
        },
        {
            "key": "curriculum_file",
            "title": "Curriculum document",
            # not shown on its own: the file is uploaded with the Upload button
            # over the programme structure table
            "hidden": True,
            "type": "fields",
            "fields": [
                {"name": "document", "label": "Curriculum Matrix (PDF, Word or Excel)", "type": "file",
                 "wide": True, "accept": ".pdf,.docx,.doc,.xlsx,.xls,.csv"},
            ],
        },
    ],
}




PROGRAMME_SYLLABUS = {
    "key": "prog_syllabus",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Syllabus — current batch",
    # shows the current batch (Admin > Settings) beside the title
    "batch": "current",
    "blurb": "",
    "per_programme": True,
    "sections": [
        {
            # one sheet per course, laid out as the syllabus template is —
            # nothing on the page but the template's own content
            "key": "courses",
            "title": "",
            "type": "table",
            "min_rows": 1,
            "display": "sheet",
            "card": {"code": "course_code", "name": "course_title", "noun": "course"},
            "columns": [
                # Course Information: the course's own line of the Curriculum table —
                # its semester, credits, L-T-P-E and CA : ESE come from there, not typed again
                {"name": "course_title", "label": "Course Title", "type": "text", "required": True},
                {"name": "course_code", "label": "Course Code", "type": "text", "required": True},
                {"name": "semester", "label": "Semester", "type": "integer", "min": 1, "max": 10,
                 "hidden": True},
                {"name": "ltpe", "label": "L-T-P-E", "type": "readonly", "hidden": True},
                {"name": "credits", "label": "Credits", "type": "number", "required": True,
                 "min": 0, "max": 20},
                {"name": "hours_per_week", "label": "Hours per week", "type": "integer",
                 "min": 0, "max": 40, "hidden": True},
                # contact hours: 15 for every credit
                {"name": "teaching_hours", "label": "Contact Hours", "type": "integer",
                 "required": True, "min": 0, "max": 600},
                {"name": "ca_ese", "label": "CA : ESE", "type": "readonly", "hidden": True},
                {"name": "objectives", "label": "Course Objectives", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 1,
                 "placeholder": "To explain …\nTo develop …  — one per line"},
                # the Course Outcomes, each with its Bloom's Taxonomy level ([{text, bloom}]);
                # "outcomes" is the same, one per line, for the checks and the exports
                {"name": "co_table", "label": "Course Outcomes and Bloom's levels", "type": "readonly",
                 "hidden": True},
                {"name": "outcomes", "label": "Course Outcomes", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 3},
                # CO-PO-PSO Mapping: one row a CO, {"PO1": "3", …, "PSO4": "-"}
                {"name": "co_po", "label": "CO-PO-PSO Mapping", "type": "readonly", "hidden": True},
                {"name": "modules", "label": "Course Content", "type": "module_compare", "compare": False,
                 "required": True},
                {"name": "text_books", "label": "Text Books", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 1,
                 "placeholder": "Author (Year). Title (edition). Publisher.  — one per line"},
                {"name": "books", "label": "Book References", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 1,
                 "placeholder": "Author: Year, Title, Publisher  — one per line"},
                {"name": "web_references", "label": "Web References", "type": "textarea", "rows": 3,
                 "placeholder": "Name of the site  https://…  — one per line"},
                # kept from the earlier template, now optional
                {"name": "pedagogy", "label": "Pedagogy", "type": "textarea",
                 "rows": 2, "placeholder": "Classrooms lecture, Case studies, Tutorial Classes, "
                                           "Group discussion, Seminar & field work etc.,"},
                {"name": "skill_activities", "label": "Skill Development Activities", "type": "textarea",
                 "rows": 4, "placeholder": "1. …\n2. …  — one per line"},
            ],
            "rules": ["course_codes_known", "bloom_verbs_present", "outcomes_have_bloom_levels",
                      "co_po_mapping_valid"],
        },
    ],
}


REVISION_TYPES = ["Major Revision", "Minor Revision"]

def _plain_syllabus(key: str, title: str, blurb: str) -> dict:
    """The syllabus template, as another form: Course Revision and the
    earlier batches use the very same sheet."""
    import copy
    part = copy.deepcopy(PROGRAMME_SYLLABUS)
    part.pop("batch", None)
    part.update({"key": key, "title": title, "blurb": blurb})
    for sec in part["sections"]:
        if sec["key"] == "courses":
            sec["rules"] = ["bloom_verbs_present"]
    return part


# Course Revision, as the syllabus revision document lays it out (BBA
# Syllabus Revision 2024): who and when, the (A)–(D) summary with the
# course-wise % change by semester, then one module-wise table per course —
# the previous syllabus beside the revised one, % change per module and the
# average. Filled from the syllabi: revised from the current batch, previous
# from the latest earlier batch.
PROGRAMME_REVISION = {
    "key": "prog_revision",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Course Revision",
    "blurb": "",
    "per_programme": True,
    "sections": [
        {
            "key": "header",
            "title": "Percentage of change in syllabus revision for",
            "type": "fields",
            "fields": [
                {"name": "programme_name", "label": "Name of the programme", "type": "readonly",
                 "prefill": "programme_name", "wide": True},
                {"name": "programme_code", "label": "Programme code", "type": "readonly",
                 "prefill": "programme_code"},
                {"name": "department", "label": "Name of the department", "type": "readonly",
                 "prefill": "dept_name"},
                {"name": "revision_year", "label": "Year of revision", "type": "readonly",
                 "prefill": "revision_year"},
            ],
        },
        {
            "key": "revision_summary",
            "title": "Summary",
            "type": "revision_summary",
            "source": "courses",
            "threshold": 20,
        },
        {
            "key": "courses",
            "title": "Percentage of change in syllabus — module-wise for all courses",
            "type": "table",
            "min_rows": 1,
            "display": "revision",
            "columns": [
                {"name": "course_code", "label": "Subject code", "type": "text", "required": True},
                {"name": "course_title", "label": "Subject / course title", "type": "text",
                 "required": True},
                {"name": "semester", "label": "Semester", "type": "integer", "min": 1, "max": 8,
                 "choices": SEMESTERS},
                {"name": "year_previous", "label": "Year of previous revision", "type": "text",
                 "pattern": "^[0-9]{4}$"},
                {"name": "year_latest", "label": "Year of latest revision", "type": "text",
                 "pattern": "^[0-9]{4}$"},
                {"name": "prev_code", "label": "Previous subject code", "type": "text"},
                {"name": "prev_title", "label": "Previous subject / course title", "type": "text"},
                {"name": "modules", "label": "Modules", "type": "module_compare", "required": True},
                {"name": "avg_change", "label": "Average percentage on revision", "type": "readonly"},
            ],
        },
    ],
}


PARTS = [PROGRAMME_CURRICULUM, PROGRAMME_SYLLABUS, PROGRAMME_REVISION]


# --------------------------------------------------------------------------
# Syllabi of earlier batches — the same template, one form per batch year.
# Which years are shown is set in Admin > Settings; a form exists for every
# year from 2010 so a year can be added without a code change. They are a
# record, not part of the gate: the Curriculum stage completes without them.
# --------------------------------------------------------------------------

def batch_label(start: int) -> str:
    return f"{start}–{start + 1}"


def batch_key(start: int) -> str:
    return f"prog_syllabus_b{start}"


def batch_start(label) -> int | None:
    """2024 from "2024-2025", "2024–25", "2024 to 2025" or 2024."""
    import re
    m = re.match(r"\s*((?:19|20)\d{2})", str(label or ""))
    return int(m.group(1)) if m else None


def _batch_courses_columns():
    """The programme structure's columns, for an earlier batch's courses —
    with the same Syllabus and Revision links (a → into that batch's own
    Syllabus page and into Course Revision)."""
    import copy
    sec = next(x for x in PROGRAMME_CURRICULUM["sections"] if x["key"] == "semester_structure")
    cols = [copy.deepcopy(c) for c in sec["columns"]]
    for c in cols:
        # no Yes / No on an earlier batch: each course's syllabus is typed in its Syllabus page
        if c["name"] == "syllabus":
            c["help"] = "Opens this course's syllabus in this batch's Syllabus page."
        elif c["name"] == "revision":
            c["help"] = "Opens this course on this batch's Course Revision page."
    return cols


def _batch_part(start: int) -> dict:
    """An earlier batch's syllabus, as the current batch's is: the courses
    the batch studied (the programme structure's columns, with Syllabus and
    Revision on each row), and below them each course's syllabus — the same
    sheet as the current batch, in the syllabus template."""
    import copy
    label = batch_label(start)
    sheet = copy.deepcopy(next(x for x in PROGRAMME_SYLLABUS["sections"] if x["key"] == "courses"))
    # Course Revision for this batch's courses: the same module-by-module table
    revision = copy.deepcopy(next(x for x in PROGRAMME_REVISION["sections"] if x["key"] == "courses"))
    revision.update({
        "key": "revision_courses",
        "title": f"Course Revision — Batch of {label}",
        "help": "Each course's modules as the batch studied them beside the revised ones, with the "
                "% change. Revision → on a course of this batch's Curriculum opens it here; or fill in "
                "all its courses at once from this batch's Syllabus.",
        "min_rows": 0,
    })
    sheet.update({
        "title": f"Syllabus — Batch of {label}",
        "help": "Each course's syllabus for this batch. Syllabus → on a course of this batch's Curriculum "
                "opens it here; or fill in all its courses at once.",
        "min_rows": 0,
        # its courses are this batch's own, not the current programme structure's
        "rules": ["bloom_verbs_present", "outcomes_have_bloom_levels", "co_po_mapping_valid"],
    })
    return {
        "key": batch_key(start),
        "parent": "curriculum",
        "group": "Stage 3 · Curriculum",
        "title": f"Syllabus — Batch of {label}",
        "blurb": "",
        "per_programme": True,
        "batch": label, "existing_batch": True, "optional": False,
        "sections": [{
            "key": "batch_courses",
            "title": f"Curriculum — Batch of {label}",
            "help": "The courses this batch studied, one per row, as in the programme structure. "
                    "Syllabus → opens the course on this batch's Syllabus page; Revision → opens it on its Course Revision page.",
            "type": "table",
            "min_rows": 0,
            "columns": _batch_courses_columns(),
            "rules": ["ltpe_credit_arithmetic", "marks_add_up", "unique_course_codes", "batch_has_courses",
                      "semester_within_batch"],
        }, sheet, revision],
    }


BATCH_PARTS = [_batch_part(y) for y in range(2010, 2041)]
DEFAULT_CURRENT_BATCH = "2026-2027"
DEFAULT_EXISTING_BATCHES = ["2024-2025", "2025-2026"]

CURRICULUM = {
    "key": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Curriculum",
    "blurb": "Every programme mapped to the department, UG and PG. Open a programme to fill its "
             "Curriculum, Syllabus and Course Revision.",
    "per_programme": True,
    "parts": [p["key"] for p in PARTS],
    "sections": [],
}


# --------------------------------------------------------------------------
# Ordered stage list  — this order IS the lock order
# --------------------------------------------------------------------------

STAGES = [
    DEPARTMENT_INFORMATION,
    PRE_BOS,
    BOS_DOCUMENTS,
    CURRICULUM,
]

STAGE_KEYS = [s["key"] for s in STAGES]
# every form that can be opened, the per-programme parts included
STAGE_BY_KEY = {s["key"]: s for s in STAGES + PARTS + BATCH_PARTS}
PART_KEYS = [p["key"] for p in PARTS]

GROUP_ORDER = [s["group"] for s in STAGES]


def is_pg(degree_level) -> bool:
    """PG and PG Diploma programmes fill the PG Course Matrix."""
    return programme_level(degree_level) in ("PG", "PGD") if degree_level else False


def for_level(stage: dict, degree_level) -> dict:
    """The Curriculum form as a programme of this level fills it. A PG
    programme has no Honours tracks or minors, states its fee, and opens
    with the PG wording; a UG programme is as it was. Both choose a course's
    category from the same list."""
    import copy
    if stage and stage.get("existing_batch"):
        # an earlier batch's course list follows the programme's level too
        if not (is_pg(degree_level) or degree_level == "UG - 3 Year"):
            return stage
        s = copy.deepcopy(stage)
        for sec in s["sections"]:
            if sec["key"] != "batch_courses":
                continue
            for c in sec["columns"]:
                if c["name"] == "semester":
                    n = 4 if is_pg(degree_level) else 6
                    c["max"], c["choices"] = n, list(range(1, n + 1))
        return s
    if not stage or stage.get("key") != "prog_curriculum":
        return stage
    if degree_level == "UG - 3 Year":
        # a 3-year degree runs for six semesters
        s = copy.deepcopy(stage)
        for sec in s["sections"]:
            if sec["key"] == "semester_structure":
                for c in sec["columns"]:
                    if c["name"] == "semester":
                        c["max"], c["choices"] = 6, list(range(1, 7))
        return s
    if not is_pg(degree_level):
        return stage
    s = copy.deepcopy(stage)
    s["level"] = "PG"
    s["sections"] = [sec for sec in s["sections"] if sec["key"] != "minors"]
    for sec in s["sections"]:
        if sec["key"] == "semester_structure":
            sec["columns"] = list(sec["columns"])
            for c in sec["columns"]:
                if c["name"] == "semester":
                    c["max"], c["choices"] = 4, [1, 2, 3, 4]
            sec["help"] = ("One row per course, with its course category. Electives vary by programme: "
                           "list each elective a student may choose as its own row, in its semester and "
                           "category, so the choice is clear to the students.")
        elif sec["key"] == "credit_classification":
            sec["title"] = "Summary — credits by classification"
            sec["help"] = "The Credit table will be automatically populated based on the courses added to the programme structure below."
        elif sec["key"] == "credit_distribution":
            sec["title"] = "Credits by assessment"
            sec["help"] = "Worked out from the programme structure."
            sec["rules"] = [r for r in sec.get("rules", []) if not r.startswith("ugc_")]
        elif sec["key"] == "profile":
            fields = []
            for f in sec["fields"]:
                if f["name"] in PG_REGULATIONS:
                    f["prefill_text"] = PG_REGULATIONS[f["name"]]
                if f["name"] == "eligibility":
                    f["placeholder"] = ("For example: A bachelor's degree in the discipline or an allied "
                                        "one, with a minimum of 50% marks, from a recognised university.")
                if f["name"] == "assessment":
                    f["label"] = "11. Assessment"
                elif f["name"] == "passing":
                    f["label"] = "12. Standard of passing"
                elif f["name"] == "award":
                    f["label"] = "13. Award of degree / diploma / certificate"
                fields.append(f)
                if f["name"] == "course_specialisation":
                    fields.append({"name": "fee", "label": "10. Fee", "type": "textarea", "rows": 3,
                                   "wide": True, "prefill_text": PG_REGULATIONS["fee"],
                                   "help": "Academic fee p.a., Institute deposit and Total — for Indian "
                                           "students, NRI / PIO / OCI and foreign nationals."})
            sec["fields"] = fields
            sec["help"] = "Please provide the relevant details for all 13 sections as requested."
    return s


def category_groups(data: dict, degree_level, key="semester_structure") -> dict:
    """A programme's structure (or an earlier batch's course list, with
    key="batch_courses") with every course group one of the course categories
    (an older draft's Discipline Specific Elective, Generic Core and the like
    are read as the category they stand for). A PG programme has no tracks."""
    if not isinstance(data, dict):
        return data
    rows = data.get(key)
    if not isinstance(rows, list):
        return data
    pg = is_pg(degree_level)
    out = []
    for r in rows:
        if isinstance(r, dict):
            r = dict(r)
            r["nep_category"] = course_category(r.get("nep_category"), r.get("credits"), r.get("course_title"))
            if pg:
                r.pop("track", None)
        out.append(r)
    return {**data, key: out}


def programme_level(degree_level: str) -> str:
    """UG / PG / PGD, from the degree level."""
    d = str(degree_level or "")
    if d.startswith("PG Diploma"):
        return "PGD"
    return "PG" if d.startswith("PG") else "UG"


def degree_tag(degree_level) -> str:
    """What a UG programme's name carries: (3 Years), (Honours) or (Honours with Research)."""
    return {"UG - 3 Year": "3 Years", "UG - 4 Year (Honours)": "Honours",
            "UG - 4 Year (Honours with Research)": "Honours with Research"}.get(degree_level or "", "")


# "(Honours)", "(3 Years)" — or one typed without its closing bracket
_DEGREE_SUFFIX = re.compile(r"\s*\((?:[^()]*hon(?:ou)?r?s[^()]*|\s*\d\s*years?\s*)\)?\s*$", re.I)


def degree_name(name, degree_level) -> str:
    """A UG programme's name with the degree chosen for it: any Honours /
    years ending it already has gives way to (3 Years), (Honours) or
    (Honours with Research)."""
    tag = degree_tag(degree_level)
    name = str(name or "").strip()
    if not tag:
        # a bracket left open is closed
        return name + ")" if name.count("(") > name.count(")") else name
    return f"{_DEGREE_SUFFIX.sub('', name)} ({tag})"


def degree_years(degree_level: str):
    m = {"UG - 3 Year": 3, "UG - 4 Year (Honours)": 4, "UG - 4 Year (Honours with Research)": 4,
         "PG - 1 Year": 1, "PG - 2 Year": 2, "PG Diploma - 1 Year": 1}
    return m.get(degree_level)


def stage_index(key: str) -> int:
    return STAGE_KEYS.index(key) if key in STAGE_KEYS else -1


def previous_stage(key: str):
    i = stage_index(key)
    return STAGE_KEYS[i - 1] if i > 0 else None


def next_stage(key: str):
    i = stage_index(key)
    return STAGE_KEYS[i + 1] if 0 <= i < len(STAGE_KEYS) - 1 else None


def all_fields(stage: dict):
    """Yield (section, field) for every field in a stage, tables included."""
    for section in stage.get("sections", []):
        if section.get("type") == "table":
            for col in section.get("columns", []):
                yield section, col
        elif section.get("type") == "fields":
            for f in section.get("fields", []):
                yield section, f
