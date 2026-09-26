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

NEP_CATEGORIES = [
    "Major (Core)",
    "Minor Stream",
    "Multidisciplinary",
    "Ability Enhancement Courses (AEC)",
    "Skill Enhancement Courses (SEC)",
    "Value Added Courses (VAC)",
    "Summer Internship",
    "Research Project / Dissertation",
    "Mandatory Non-Credit Course",
    "Mandatory Non-Credit Audit Course",
]

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
    "blurb": "Confirm the department record and the programmes mapped to it. Every programme "
             "kept here appears in the Curriculum stage.",
    "sections": [
        {
            "key": "identity",
            "title": "Department identity",
            "type": "fields",
            # shown as cards; the pencil opens the fields for editing
            "display": "cards",
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
            "help": "The programmes the Office of Academics has on record for your department. "
                    "Keep the ones you run this year, remove the ones you do not, and add any "
                    "new programme. This list carries into the Curriculum stage.",
            "type": "programme_list",
            "degrees": ["UG", "PG", "PG-1Yr", "PGD"],
            # the tabs the list is split into, by the workbook's Degree column
            "tabs": [{"key": "UG", "label": "UG programmes", "degrees": ["UG"]},
                     {"key": "PG", "label": "PG programmes",
                      "degrees": ["PG", "PG-1Yr", "PGD"]}],
            "removal_reasons": [
                "Programme discontinued",
                "No admissions this year",
                "Merged into another programme",
                "Moved to another department",
                "Not run at this campus",
                "Listed here by mistake",
                "Other",
            ],
            "rules": ["programmes_offered_valid"],
            # what the Excel and Word exports print for each programme
            "columns": [
                {"name": "programme_code", "label": "Code"},
                {"name": "programme_name", "label": "Programme"},
                {"name": "degree", "label": "Degree"},
                {"name": "source", "label": "From"},
                {"name": "decision", "label": "Kept / removed"},
                {"name": "removal_reason", "label": "Reason for removal"},
                {"name": "removal_note", "label": "Note"},
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
    "blurb": "The date of the Board of Studies meeting and its documents.",
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
            "help": "PDF, Word, Excel or images. Where a box takes several files you can pick "
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
# Stage 3 — Curriculum: per programme, Curriculum · Syllabus · Course Revision
# --------------------------------------------------------------------------

PROGRAMME_CURRICULUM = {
    "key": "prog_curriculum",
    "parent": "curriculum",
    "group": "Stage 3 · Curriculum",
    "title": "Curriculum",
    "blurb": "The programme's details, its structure semester by semester with the credit "
             "classification checked against UGC Table 2, and items 1–12 of the Curriculum "
             "Matrix template.",
    "source_templates": [
        "Curriculum Matrix Template.docx",
        "BCom (Corporate Finance) Honours / Honours with Research V1 25 Jun.docx",
    ],
    "samples": [
        {"label": "Curriculum Matrix template (blank)", "file": "docs/Curriculum_Matrix_Template.docx"},
        {"label": "Curriculum sample — BCom (Corporate Finance)",
         "file": "docs/Curriculum_Sample_BCom_Corporate_Finance.docx"},
    ],
    "per_programme": True,
    "sections": [
        {
            "key": "details",
            "title": "Programme details",
            "help": "Code and name come from Department Information. Choose the degree first — "
                    "the UGC credit check follows it.",
            "type": "fields",
            "fields": [
                {"name": "programme_code", "label": "Programme code", "type": "readonly",
                 "prefill": "programme_code"},
                {"name": "programme_name", "label": "Programme", "type": "readonly",
                 "prefill": "programme_name", "wide": True},
                {"name": "degree_level", "label": "Degree / Duration", "type": "select",
                 "required": True, "options": DEGREE_LEVELS, "prefill": "degree_level",
                 "reload_on_change": True},
                {"name": "specialisation", "label": "Specialisation", "type": "text"},
                {"name": "batch", "label": "Batch", "type": "text", "required": True,
                 "pattern": "^[0-9]{4}\\s*-\\s*[0-9]{2,4}$", "help": "For example 2026-30."},
            ],
        },
        {
            "key": "profile",
            "title": "Regulations — programme profile",
            "help": "Items 1 to 12 of the Curriculum Matrix template. The university-wide "
                    "wording is filled in from the sample; change only what differs for this "
                    "programme.",
            "type": "fields",
            "fields": [
                {"name": "objective", "label": "1. Objective", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 2, "wide": True,
                 "help": "Two to six objectives, one per line, each beginning with a Bloom's "
                         "taxonomy action verb."},
                {"name": "duration_months", "label": "2. Duration (in months)", "type": "integer",
                 "required": True, "min": 6, "max": 72},
                {"name": "intake", "label": "3. Intake", "type": "integer", "required": True,
                 "min": 1, "max": 2000},
                {"name": "reservation_policy", "label": "4. Reservation", "type": "fixed", "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["reservation_policy"],
                 "fixed_table": [
                     {"head": "I. Within the sanctioned Intake",
                      "items": ["a) SC (In Percentage)", "b) ST (In Percentage)",
                                "c) Differently abled (In Percentage)",
                                "d) Defence (In Percentage)"],
                      "note": DEFAULT_REGULATIONS["reservation_policy"]},
                     {"head": "II. Over and above the sanctioned Intake",
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
                 "placeholder": "For example: BCom (Corporate Finance) Honours / Honours with "
                                "Research — minors as per Annexure I"},
                {"name": "assessment", "label": "10. Assessment", "type": "textarea",
                 "required": True, "rows": 3, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["assessment"]},
                {"name": "passing", "label": "11. Standard of passing", "type": "textarea",
                 "required": True, "rows": 4, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["passing"]},
                {"name": "award", "label": "12. Award of degree / diploma / certificate",
                 "type": "textarea", "required": True, "rows": 4, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["award"]},
            ],
        },
        {
            "key": "credit_classification",
            "title": "Classification of Credits and Number of Non-Credit Courses",
            "help": "Worked out from the programme structure below — credits per semester in "
                    "each course group, and the mandatory non-credit and audit courses. Nothing "
                    "to type here.",
            "type": "credit_distribution",
            "show": "classification",
        },
        {
            "key": "semester_structure",
            "title": "Programme structure — semester scheme",
            "help": "One row per course, semester by semester, grouped the way the template "
                    "groups them (Major, Minor, AEC, VAC, SEC …). For a 4-year programme, mark "
                    "semester 7 and 8 courses as Honours or Honours with Research. A Minor or "
                    "Multi-disciplinary slot may be left without a code.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 10, "width": "84px"},
                {"name": "track", "label": "Applies to", "type": "select", "options": TRACKS,
                 "width": "150px", "help": "Leave as All semesters except for semester 7 and 8 "
                                           "courses that differ between the two tracks."},
                {"name": "nep_category", "label": "Course group", "type": "select", "required": True,
                 "options": NEP_CATEGORIES},
                {"name": "course_code", "label": "Course code", "type": "text",
                 "pattern": "^[A-Za-z0-9][A-Za-z0-9 /\\-.]{1,60}$", "width": "130px",
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
                {"name": "cia", "label": "Continuous Assessment marks", "type": "integer",
                 "required": True, "min": 0, "max": 500, "width": "96px"},
                {"name": "ese", "label": "Term End Examination marks", "type": "integer",
                 "required": True, "min": 0, "max": 500, "width": "96px"},
                {"name": "total_marks", "label": "Total marks", "type": "integer", "required": True,
                 "min": 0, "max": 1000, "width": "86px"},
            ],
            "rules": [
                "ltpe_credit_arithmetic",
                "credit_marks_ratio",
                "marks_add_up",
                "semester_within_duration",
                "unique_course_codes",
            ],
        },
        {
            "key": "credit_distribution",
            "title": "Summary",
            "help": "Worked out from the programme structure above: continuous-assessment and "
                    "term-end credits and marks per semester, and the check against UGC Table 2.",
            "type": "credit_distribution",
            "show": "summary",
            "rules": ["ugc_table2_minimums", "ugc_total_credits"],
        },
        {
            "key": "minors",
            "title": "Minor / Honours — Annexure I",
            "help": "One row per minor course: the minor stream, the semester it is taught in, "
                    "and its code and title. Annexure I differs by department.",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "minor_title", "label": "Minor stream", "type": "text", "required": True,
                 "help": "For example: Analytics"},
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 10, "width": "84px"},
                {"name": "course_code", "label": "Course code", "type": "text", "width": "130px"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 0, "max": 20, "width": "76px"},
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
    "blurb": "One syllabus per course, as in the syllabus template.",
    "source_templates": ["[Template] Syllabus.pdf"],
    "per_programme": True,
    "sections": [
        {
            "key": "header",
            "title": "Programme",
            "type": "fields",
            "fields": [
                {"name": "programme_name", "label": "Name of the program", "type": "readonly",
                 "prefill": "programme_name", "wide": True},
                {"name": "batch", "label": "Batch", "type": "readonly", "prefill": "batch"},
            ],
        },
        {
            "key": "courses",
            "title": "Course syllabi",
            "help": "Every course in the programme structure gets a card — “Fill in all” adds "
                    "them with title, credits and hours already in.",
            "type": "table",
            "min_rows": 1,
            "display": "cards",
            "card": {"code": "course_code", "name": "course_title", "noun": "course"},
            "tabs": [{"key": "details", "label": "Course details"},
                     {"key": "modules", "label": "Modules & revision"},
                     {"key": "syllabus", "label": "Activities & books"}],
            "columns": [
                {"name": "course_code", "label": "Course code", "type": "text", "required": True},
                {"name": "course_title", "label": "Name of the course", "type": "text", "required": True},
                {"name": "semester", "label": "Semester", "type": "integer", "min": 1, "max": 10},
                {"name": "credits", "label": "Course credits", "type": "number", "required": True,
                 "min": 0, "max": 20},
                {"name": "hours_per_week", "label": "No. of hours per week", "type": "integer",
                 "required": True, "min": 0, "max": 40},
                {"name": "teaching_hours", "label": "Total no. of teaching hours", "type": "integer",
                 "required": True, "min": 0, "max": 600},
                {"name": "pedagogy", "label": "Pedagogy", "type": "textarea", "required": True,
                 "rows": 2, "wide": True,
                 "help": "Classroom lecture, case studies, tutorials, seminars, field work…"},
                {"name": "outcomes", "label": "Course outcomes", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 3, "wide": True,
                 "help": "On successful completion the students will be able to… One per line."},
                {"name": "year_previous", "in_table": True, "label": "Year of previous revision", "type": "text",
                 "pattern": "^[0-9]{4}$", "tab": "modules",
                 "help": "Leave empty for a course taught for the first time."},
                {"name": "year_latest", "in_table": True, "label": "Year of latest revision", "type": "text",
                 "required": True, "pattern": "^[0-9]{4}$", "tab": "modules"},
                {"name": "prev_code", "in_table": True, "label": "Previous course code", "type": "text", "tab": "modules"},
                {"name": "prev_title", "in_table": True, "label": "Previous course title", "type": "text", "tab": "modules"},
                {"name": "modules", "label": "Modules — previous and revised", "type": "module_compare",
                 "required": True, "wide": True, "tab": "modules",
                 "help": "One entry per module: the previous syllabus beside the revised one. "
                         "The % change works itself out from the two; type over it if you "
                         "assessed it differently."},
                {"name": "avg_change", "in_table": True, "label": "Average percentage on revision (all modules)",
                 "type": "readonly", "tab": "modules"},
                {"name": "skill_activities", "label": "Skill development activities", "type": "textarea",
                 "required": True, "rows": 4, "min_items": 1, "tab": "syllabus", "wide": True,
                 "help": "One per line."},
                {"name": "books", "label": "Books for reference", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 2, "tab": "syllabus", "wide": True, "help": "One per line."},
                {"name": "syllabus_file", "label": "Syllabus document", "type": "file",
                 "accept": ".pdf,.docx,.doc", "tab": "syllabus", "help": "Optional."},
            ],
            "rules": ["course_codes_known", "bloom_verbs_present"],
        },
        {
            "key": "revision_summary",
            "title": "Percentage of change in syllabus revision",
            "help": "Worked out from the courses above: (A) courses, (B) courses revised above "
                    "20%, (C) = B / A × 100, (D) average percentage revised, and the course-wise "
                    "change for every semester.",
            "type": "revision_summary",
            "source": "courses",
            "threshold": 20,
        },
    ],
}


REVISION_TYPES = ["Major Revision", "Minor Revision"]

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
            "help": "One card per revised or new course. Leave empty if nothing was revised.",
            "type": "table",
            "min_rows": 0,
            "display": "cards",
            "card": {"code": "revised_code", "name": "revised_title", "noun": "revision"},
            "tabs": [{"key": "details", "label": "Revision"},
                     {"key": "content", "label": "Content & feedback"}],
            "columns": [
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 10},
                {"name": "code_before", "label": "Course code (before revision)", "type": "text",
                 "help": "N/A for a new course."},
                {"name": "title_before", "label": "Course title (before revision)", "type": "text"},
                {"name": "revision_type", "label": "Type of revision", "type": "select", "required": True,
                 "options": REVISION_TYPES},
                {"name": "percent_change", "label": "% change", "type": "integer", "required": True,
                 "min": 0, "max": 100},
                {"name": "revised_code", "label": "Revised course code (if major revision)", "type": "text"},
                {"name": "revised_title", "label": "Revised course title (if changed)", "type": "text",
                 "required": True},
                {"name": "modifications", "label": "Modifications / updates made (content, structure "
                 "or assessment)", "type": "textarea", "required": True, "rows": 2, "wide": True},
                {"name": "rationale", "label": "Overall rationale for revision", "type": "textarea",
                 "required": True, "rows": 2, "wide": True},
                {"name": "module_nos", "label": "Module nos. where revisions are made", "type": "text",
                 "tab": "content"},
                {"name": "existing_content", "label": "Existing content", "type": "textarea", "rows": 2,
                 "tab": "content", "wide": True},
                {"name": "proposed_content", "label": "Proposed content", "type": "textarea",
                 "required": True, "rows": 2, "tab": "content", "wide": True},
                {"name": "introduced_year", "label": "Introduction of the course for the first time "
                 "in the program (year)", "type": "text", "tab": "content"},
                {"name": "previous_revision", "label": "Year/s of previous revision", "type": "text",
                 "tab": "content"},
                {"name": "feedback_from", "label": "Stakeholder feedback from", "type": "select",
                 "options": ["Industry", "Academia", "Alumni", "Student", "Others"], "tab": "content"},
                {"name": "key_suggestions", "label": "Key suggestions", "type": "textarea", "rows": 2,
                 "tab": "content", "wide": True},
                {"name": "remarks", "label": "Remarks, if any", "type": "textarea", "rows": 2,
                 "tab": "content", "wide": True},
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
# every form that can be opened, the per-programme parts included
STAGE_BY_KEY = {s["key"]: s for s in STAGES + PARTS}
PART_KEYS = [p["key"] for p in PARTS]

GROUP_ORDER = [s["group"] for s in STAGES]


def programme_level(degree_level: str) -> str:
    """UG / PG / PGD, from the degree level."""
    d = str(degree_level or "")
    if d.startswith("PG Diploma"):
        return "PGD"
    return "PG" if d.startswith("PG") else "UG"


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
