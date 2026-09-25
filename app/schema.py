"""
Declarative field schema for the BoS Data Repository.

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
               added/removed by the user. `layout: "cards"` shows each row as
               a card instead of a table row.
    credit_matrix -> the UGC Table 2 tally

AUTO-FILL
    prefill   -> filled from the department / programme record on first open;
                 readonly fields are refreshed every time
    calc      -> computed in the row (credits_from_ltpe, cia_plus_ese)
    lookup    -> a select whose options are the programme's courses; `fills`
                 copies the course's details into the row
    count     -> counts rows of another table with a given value
"""

# --------------------------------------------------------------------------
# Shared option lists
# --------------------------------------------------------------------------

CAMPUSES = ["Bengaluru", "Kochi"]

DEGREE_LEVELS = [
    "UG - 3 Year",
    "UG - 4 Year (Honours)",
    "UG - 4 Year (Honours with Research)",
    "PG - 1 Year",
    "PG - 2 Year",
    "PG Diploma - 1 Year",
]

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
# Level 0 — Department Information  (and the programmes mapped to it)
# --------------------------------------------------------------------------

DEPARTMENT_INFORMATION = {
    "key": "dept_info",
    "group": "Level 0 · Department",
    "title": "Department Information",
    "blurb": "Confirm the department record and list every programme the department runs. "
             "The programmes listed here appear in the Curriculum stage.",
    "sections": [
        {
            "key": "identity",
            "title": "Department identity",
            "type": "fields",
            "fields": [
                {"name": "dept_name", "label": "Department name", "type": "text", "required": True,
                 "prefill": "dept_name", "help": "Exactly as it appears on official university records."},
                {"name": "school", "label": "School / Faculty", "type": "text", "required": True,
                 "prefill": "school"},
                {"name": "dept_code", "label": "Department code", "type": "text", "required": True,
                 "prefill": "dept_code", "pattern": "^[A-Za-z0-9\\-/]{2,20}$",
                 "help": "Letters, numbers, hyphen or slash only."},
                {"name": "campus", "label": "Campus / Location", "type": "select", "required": True,
                 "options": CAMPUSES, "prefill": "campus"},
                {"name": "campus_address", "label": "Campus address", "type": "textarea", "required": True,
                 "rows": 3},
                {"name": "academic_year", "label": "Academic year", "type": "readonly", "prefill": "academic_year"},
            ],
        },
        {
            "key": "contact",
            "title": "Department contact",
            "type": "fields",
            "fields": [
                {"name": "office_email", "label": "Department office email", "type": "email", "required": True},
                {"name": "office_phone", "label": "Department landline / extension", "type": "phone"},
                {"name": "faculty_count", "label": "Number of full-time faculty", "type": "integer",
                 "required": True, "min": 0, "max": 1000},
            ],
        },
        {
            "key": "programmes",
            "title": "Programmes mapped to this department",
            "help": "One row per programme (UG and PG). Each programme gets its own Curriculum, "
                    "Syllabus and Course Revision in the Curriculum stage.",
            "type": "table",
            "min_rows": 1,
            "programme_source": True,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "programme_name", "label": "Programme name", "type": "text", "required": True,
                 "help": "For example: BCom (Corporate Finance) Honours / Honours with Research"},
                {"name": "programme_code", "label": "Programme code", "type": "text", "required": True,
                 "pattern": "^[A-Za-z0-9\\-]{2,20}$", "help": "Letters, numbers or hyphen. Example BCOM-CF"},
                {"name": "degree_level", "label": "Degree / Duration", "type": "select", "required": True,
                 "options": DEGREE_LEVELS},
                {"name": "specialisation", "label": "Specialisation", "type": "text"},
                {"name": "batch", "label": "Batch", "type": "text", "required": True,
                 "pattern": "^[0-9]{4}\\s*-\\s*[0-9]{2,4}$", "help": "For example 2026-30 or 2026-2030."},
            ],
            "rules": ["programme_unique_codes"],
        },
    ],
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
            "help": "Fill the university templates offline, have them signed, and upload them "
                    "here as PDF or Word files.",
            "type": "fields",
            "fields": [
                {"name": "diac_signed",
                 "label": "Composition of the Department Industry-Academia Cell (DIAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "dpac_signed",
                 "label": "Composition of the Department Programme Assessment Committee (DPAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "notes", "label": "Note to the Office of Academics", "type": "textarea",
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
    "blurb": "Upload the Board of Studies meeting documents.",
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
            "help": "PDF, Word, Excel or images. Where a box allows several files you can pick "
                    "them all at once.",
            "type": "fields",
            "fields": [
                {"name": "bos_composition", "label": "Composition of BoS Members", "type": "file",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "vision_mission",
                 "label": "Department Vision, Mission and Program Overview", "type": "file",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "minutes", "label": "Minutes of Meeting", "type": "file",
                 "required": True, "wide": True, "accept": ".pdf,.docx,.doc"},
                {"name": "geotagged_photos", "label": "Geotagged photos of the meeting", "type": "file",
                 "required": True, "wide": True, "multiple": True,
                 "accept": ".jpg,.jpeg,.png,.pdf,.zip"},
                {"name": "external_profiles", "label": "Profiles of External Members", "type": "file",
                 "required": True, "wide": True, "multiple": True, "accept": ".pdf,.docx,.doc,.zip"},
                {"name": "attendance", "label": "Scanned Attendance Sheet", "type": "file",
                 "required": True, "wide": True, "accept": ".pdf,.jpg,.jpeg,.png"},
                {"name": "feedback_curriculum",
                 "label": "Stakeholder Feedback (For Curriculum Design and Development)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.xlsx"},
                {"name": "feedback_new_programme", "label": "Stakeholder Feedback (New Program)",
                 "type": "file", "wide": True, "accept": ".pdf,.docx,.xlsx",
                 "help": "Only if the department is proposing a new programme."},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 3 — Curriculum  (per programme: Curriculum · Syllabus · Course Revision)
# --------------------------------------------------------------------------

REVISION_TYPES = ["Major Revision", "Minor Revision"]

PROGRAMME_CURRICULUM = {
    "key": "prog_curriculum",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Curriculum",
    "blurb": "Programme details and programme structure, as in the Curriculum Matrix template.",
    "source_templates": ["Curriculum Matrix Template.docx"],
    "per_programme": True,
    "sections": [
        {
            "key": "overview",
            "title": "Programme details",
            "type": "fields",
            "fields": [
                {"name": "programme_name", "label": "Programme", "type": "readonly",
                 "prefill": "programme_name"},
                {"name": "degree_level", "label": "Degree / Duration", "type": "readonly",
                 "prefill": "degree_level"},
                {"name": "batch", "label": "Programme structure (batch)", "type": "readonly",
                 "prefill": "batch"},
                {"name": "objective", "label": "Objective", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 2, "wide": True,
                 "help": "2 to 6 points, one per line, written with Bloom's taxonomy verbs."},
                {"name": "duration_months", "label": "Duration (in months)", "type": "integer",
                 "required": True, "min": 6, "max": 72, "prefill": "duration_months"},
                {"name": "intake", "label": "Intake", "type": "integer", "required": True,
                 "min": 1, "max": 2000},
                {"name": "eligibility", "label": "Eligibility", "type": "textarea", "required": True,
                 "rows": 2},
                {"name": "selection_procedure", "label": "Selection procedure", "type": "textarea",
                 "required": True, "rows": 2},
                {"name": "medium", "label": "Medium of instruction", "type": "text", "required": True,
                 "prefill": "medium"},
                {"name": "programme_pattern", "label": "Programme pattern", "type": "text",
                 "required": True, "prefill": "programme_pattern"},
                {"name": "course_specialisation", "label": "Course & specialisation", "type": "text",
                 "required": True, "prefill": "specialisation"},
                {"name": "assessment", "label": "Assessment", "type": "textarea", "required": True,
                 "rows": 2},
                {"name": "standard_of_passing", "label": "Standard of passing", "type": "textarea",
                 "required": True, "rows": 2},
                {"name": "award", "label": "Award of Degree / Diploma / Certificate",
                 "type": "textarea", "required": True, "rows": 2},
            ],
        },
        {
            "key": "reservation",
            "title": "Reservation",
            "help": "Reservation policy as prescribed by the Central Government and UGC guidelines.",
            "type": "fields",
            "fields": [
                {"name": "sc", "label": "SC (%)", "type": "number", "min": 0, "max": 100},
                {"name": "st", "label": "ST (%)", "type": "number", "min": 0, "max": 100},
                {"name": "differently_abled", "label": "Differently abled (%)", "type": "number",
                 "min": 0, "max": 100},
                {"name": "defence", "label": "Defence (%)", "type": "number", "min": 0, "max": 100},
                {"name": "kashmiri_migrants", "label": "Kashmiri migrants (seats, over intake)",
                 "type": "integer", "min": 0, "max": 500},
                {"name": "international", "label": "International students (%, over intake)",
                 "type": "number", "min": 0, "max": 100},
            ],
        },
        {
            "key": "structure",
            "title": "Programme structure",
            "help": "One row per course, semester by semester. Credits and total marks fill in "
                    "by themselves from L-T-P-E and the marks you enter.",
            "type": "table",
            "min_rows": 1,
            "feeds_credit_matrix": True,
            "columns": [
                {"name": "semester", "label": "Sem", "type": "integer", "required": True,
                 "min": 1, "max": 10, "width": "60px"},
                {"name": "nep_category", "label": "Category", "type": "select", "required": True,
                 "options": NEP_CATEGORIES},
                {"name": "course_code", "label": "Course code", "type": "text", "required": True,
                 "pattern": "^[A-Za-z0-9.\\-]{3,20}$", "help": "Example 26BCC1C01"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "l", "label": "L", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "50px", "help": "Lecture hours per week"},
                {"name": "t", "label": "T", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "50px", "help": "Tutorial hours per week"},
                {"name": "p", "label": "P", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "50px", "help": "Practical hours per week"},
                {"name": "e", "label": "E", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "50px", "help": "Experiential hours per week"},
                {"name": "credits", "label": "Credits", "type": "number", "required": True,
                 "min": 0, "max": 20, "width": "70px", "calc": "credits_from_ltpe"},
                {"name": "cia", "label": "Continuous assessment", "type": "integer", "required": True,
                 "min": 0, "max": 500, "width": "90px"},
                {"name": "ese", "label": "Term end exam", "type": "integer", "required": True,
                 "min": 0, "max": 500, "width": "90px"},
                {"name": "total_marks", "label": "Total marks", "type": "integer", "required": True,
                 "min": 0, "max": 1000, "width": "80px", "calc": "cia_plus_ese"},
            ],
            "rules": ["ltpe_credit_arithmetic", "marks_add_up", "semester_within_duration",
                      "unique_course_codes", "category_totals_match_summary"],
        },
        {
            "key": "credit_summary",
            "title": "Classification of credits",
            "help": "Totalled automatically from the programme structure above and checked "
                    "against UGC Table 2.",
            "type": "credit_matrix",
            "rules": ["ugc_table2_minimums", "ugc_total_credits", "ugc_research_or_lieu"],
        },
        {
            "key": "minors",
            "title": "Annexure I — Minor",
            "help": "Optional. Differs by department.",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "semester", "label": "Sem", "type": "integer", "min": 1, "max": 10,
                 "width": "60px"},
                {"name": "minor_title", "label": "Minor stream", "type": "text", "required": True},
                {"name": "course_code", "label": "Course code", "type": "text", "required": True},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
            ],
        },
        {
            "key": "curriculum_file",
            "title": "Curriculum document",
            "type": "fields",
            "fields": [
                {"name": "document", "label": "Curriculum Matrix (Word or PDF)", "type": "file",
                 "wide": True, "accept": ".docx,.doc,.pdf", "help": "Optional."},
            ],
        },
    ],
}


PROGRAMME_SYLLABUS = {
    "key": "prog_syllabus",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Syllabus",
    "blurb": "One syllabus per course, as in the syllabus template. Courses come from the "
             "programme structure in Curriculum.",
    "source_templates": ["[Template] Syllabus.pdf"],
    "per_programme": True,
    "sections": [
        {
            "key": "header",
            "title": "Programme",
            "type": "fields",
            "fields": [
                {"name": "programme_name", "label": "Name of the program", "type": "readonly",
                 "prefill": "programme_name"},
                {"name": "batch", "label": "Batch", "type": "readonly", "prefill": "batch"},
            ],
        },
        {
            "key": "courses",
            "title": "Course syllabi",
            "help": "Pick a course code — title, credits and hours fill in from the programme "
                    "structure.",
            "type": "table",
            "layout": "cards",
            "min_rows": 1,
            "columns": [
                {"name": "course_code", "label": "Course code", "type": "select", "required": True,
                 "lookup": "courses",
                 "fills": {"course_title": "course_title", "credits": "credits",
                           "hours_per_week": "hours_per_week", "teaching_hours": "teaching_hours"}},
                {"name": "course_title", "label": "Name of the course", "type": "text", "required": True},
                {"name": "credits", "label": "Course credits", "type": "number", "required": True,
                 "min": 0, "max": 20},
                {"name": "hours_per_week", "label": "No. of hours per week", "type": "integer",
                 "required": True, "min": 0, "max": 40},
                {"name": "teaching_hours", "label": "Total no. of teaching hours", "type": "integer",
                 "required": True, "min": 0, "max": 600},
                {"name": "pedagogy", "label": "Pedagogy", "type": "textarea", "required": True,
                 "rows": 2, "help": "Classroom lecture, case studies, tutorials, seminars, field work…"},
                {"name": "outcomes", "label": "Course outcomes", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 3,
                 "help": "On successful completion the students will be able to… One per line."},
                {"name": "modules", "label": "Syllabus (modules)", "type": "textarea", "required": True,
                 "rows": 8, "min_items": 1,
                 "help": "One module per line: Module 1: Title (12 Hrs) – content."},
                {"name": "skill_activities", "label": "Skill development activities", "type": "textarea",
                 "required": True, "rows": 4, "min_items": 1, "help": "One per line."},
                {"name": "books", "label": "Books for reference", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 2, "help": "One per line."},
                {"name": "syllabus_file", "label": "Syllabus document", "type": "file",
                 "accept": ".pdf,.docx,.doc", "help": "Optional."},
            ],
            "rules": ["course_codes_known", "bloom_verbs_present"],
        },
    ],
}


PROGRAMME_REVISION = {
    "key": "prog_revision",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Course Revision",
    "blurb": "The Course Revision Log for this programme.",
    "source_templates": ["Course Revisions Log_Template_2026.xlsx"],
    "per_programme": True,
    "sections": [
        {
            "key": "header",
            "title": "Course Revision Log",
            "type": "fields",
            "fields": [
                {"name": "department", "label": "Department", "type": "readonly", "prefill": "dept_name"},
                {"name": "programme", "label": "Program", "type": "readonly", "prefill": "programme_name"},
                {"name": "specialisation", "label": "Specialization", "type": "readonly",
                 "prefill": "specialisation"},
                {"name": "degree_level", "label": "Degree level (UG/PG/PGD)", "type": "readonly",
                 "prefill": "level"},
                {"name": "bos_date", "label": "BoS date", "type": "readonly", "prefill": "bos_date"},
                {"name": "major_count", "label": "No. of courses with major revisions", "type": "readonly",
                 "count": {"section": "revisions", "field": "revision_type", "value": "Major Revision"}},
                {"name": "minor_count", "label": "No. of courses with minor revisions", "type": "readonly",
                 "count": {"section": "revisions", "field": "revision_type", "value": "Minor Revision"}},
                {"name": "prepared_by", "label": "Revision log prepared by", "type": "text", "required": True},
                {"name": "approved_by", "label": "Approved by HoD", "type": "text", "required": True},
            ],
        },
        {
            "key": "revisions",
            "title": "Revised courses",
            "help": "One entry per revised or new course. Leave empty if nothing was revised.",
            "type": "table",
            "layout": "cards",
            "min_rows": 0,
            "columns": [
                {"name": "sl", "label": "Sl. No", "type": "integer", "auto_index": True},
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 10},
                {"name": "code_before", "label": "Course code (before revision)", "type": "text",
                 "help": "N/A for a new course."},
                {"name": "title_before", "label": "Course title (before revision)", "type": "text"},
                {"name": "revision_type", "label": "Type of revision", "type": "select", "required": True,
                 "options": REVISION_TYPES},
                {"name": "percent_change", "label": "% change", "type": "integer", "required": True,
                 "min": 0, "max": 100},
                {"name": "revised_code", "label": "Revised course code (if major revision)", "type": "text",
                 "lookup": "courses",
                 "fills": {"revised_title": "course_title"}},
                {"name": "revised_title", "label": "Revised course title (if changed)", "type": "text"},
                {"name": "modifications", "label": "Modifications / updates made (content, structure "
                 "or assessment)", "type": "textarea", "required": True, "rows": 2},
                {"name": "rationale", "label": "Overall rationale for revision", "type": "textarea",
                 "required": True, "rows": 2},
                {"name": "module_nos", "label": "Module nos. where revisions are made", "type": "text"},
                {"name": "existing_content", "label": "Existing content", "type": "textarea", "rows": 2},
                {"name": "proposed_content", "label": "Proposed content", "type": "textarea",
                 "required": True, "rows": 2},
                {"name": "introduced_year", "label": "Introduction of the course for the first time "
                 "in the program (year)", "type": "text"},
                {"name": "previous_revision", "label": "Year/s of previous revision", "type": "text"},
                {"name": "feedback_from", "label": "Stakeholder feedback from", "type": "select",
                 "options": ["Industry", "Academia", "Alumni", "Student", "Others"]},
                {"name": "key_suggestions", "label": "Key suggestions", "type": "textarea", "rows": 2},
                {"name": "remarks", "label": "Remarks, if any", "type": "textarea", "rows": 2},
            ],
        },
        {
            "key": "revision_file",
            "title": "Revision log document",
            "type": "fields",
            "fields": [
                {"name": "document", "label": "Signed Course Revision Log (Excel or PDF)", "type": "file",
                 "wide": True, "accept": ".xlsx,.xls,.pdf", "help": "Optional."},
            ],
        },
    ],
}

PARTS = [PROGRAMME_CURRICULUM, PROGRAMME_SYLLABUS, PROGRAMME_REVISION]

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
# Every form that can be opened, the per-programme parts included.
STAGE_BY_KEY = {s["key"]: s for s in STAGES + PARTS}
PART_KEYS = [p["key"] for p in PARTS]

GROUP_ORDER = [s["group"] for s in STAGES]


def stage_index(key: str) -> int:
    return STAGE_KEYS.index(key) if key in STAGE_KEYS else -1


def previous_stage(key: str):
    i = stage_index(key)
    return STAGE_KEYS[i - 1] if i > 0 else None


def next_stage(key: str):
    i = stage_index(key)
    return STAGE_KEYS[i + 1] if 0 <= i < len(STAGE_KEYS) - 1 else None


def programme_level(degree_level: str) -> str:
    """UG / PG / PGD, from the degree level chosen in Level 0."""
    d = str(degree_level or "")
    if d.startswith("PG Diploma"):
        return "PGD"
    return "PG" if d.startswith("PG") else "UG"


def degree_years(degree_level: str):
    m = {"UG - 3 Year": 3, "UG - 4 Year (Honours)": 4, "UG - 4 Year (Honours with Research)": 4,
         "PG - 1 Year": 1, "PG - 2 Year": 2, "PG Diploma - 1 Year": 1}
    return m.get(degree_level)


def all_fields(stage: dict):
    """Yield (section, field) for every field in a stage, tables included."""
    for section in stage.get("sections", []):
        if section.get("type") == "table":
            for col in section.get("columns", []):
                yield section, col
        elif section.get("type") == "fields":
            for f in section.get("fields", []):
                yield section, f
