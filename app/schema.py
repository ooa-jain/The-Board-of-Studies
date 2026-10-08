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

# every course in the programme structure is marked out of this
MARKS_TOTAL = 100

# the semesters a course can sit in — picked from a list, never typed
SEMESTERS = list(range(1, 9))

NEP_CATEGORIES = [
    "Major (Core)",
    "Discipline Specific Elective (DSE)",
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
            "help": "Keep the programmes you run this year, remove the rest, add any new one.",
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
            "help": "Fill the templates, sign them and upload them.",
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
            # one row per document, opened with a click to upload
            "display": "accordion",
            "help": "Click a document to upload it.",
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
            "help": "Items 1 to 12. The standard wording is filled in — change only what differs.",
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
            "help": "Worked out from the programme structure — nothing to type.",
            "type": "credit_distribution",
            "show": "classification",
        },
        {
            "key": "semester_structure",
            "title": "Programme structure — semester scheme",
            "help": "One row per course. In a 4-year programme, mark semester 7 and 8 courses Honours or Honours with Research.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 8, "choices": SEMESTERS, "width": "64px"},
                {"name": "track", "label": "Applies to", "type": "select", "options": TRACKS,
                 "width": "112px", "help": "Leave as All semesters except for semester 7 and 8 "
                                           "courses that differ between the two tracks."},
                {"name": "nep_category", "label": "Course group", "type": "select", "required": True,
                 "options": NEP_CATEGORIES},
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
                {"name": "cia", "label": "Continuous Assessment marks", "type": "integer",
                 "required": True, "min": 0, "max": MARKS_TOTAL, "complement": "ese"},
                {"name": "ese", "label": "Term End Examination marks", "type": "integer",
                 "required": True, "min": 0, "max": MARKS_TOTAL, "complement": "cia"},
                {"name": "total_marks", "label": "Total marks", "type": "integer", "required": True,
                 "min": MARKS_TOTAL, "max": MARKS_TOTAL, "fixed_value": MARKS_TOTAL},
                {"name": "syllabus", "label": "Syllabus", "type": "syllabus_link",
                 "help": "Opens this course's syllabus — matched by course code and title."},
            ],
            "rules": [
                "ltpe_credit_arithmetic",
                "marks_add_up",
                "semester_within_duration",
                "unique_course_codes",
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
            "help": "One row per minor course.",
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
                {"name": "course_code", "label": "Course Code", "type": "text", "required": True},
                {"name": "course_title", "label": "Name of the Course", "type": "text", "required": True},
                # kept for the curriculum link and the order of courses; not on the sheet
                {"name": "semester", "label": "Semester", "type": "integer", "min": 1, "max": 10,
                 "hidden": True},
                {"name": "credits", "label": "Course Credits", "type": "number", "required": True,
                 "min": 0, "max": 20},
                {"name": "hours_per_week", "label": "No. of Hours per Week", "type": "integer",
                 "required": True, "min": 0, "max": 40},
                {"name": "teaching_hours", "label": "Total No. of Teaching Hours", "type": "integer",
                 "required": True, "min": 0, "max": 600},
                {"name": "pedagogy", "label": "Pedagogy", "type": "textarea", "required": True,
                 "rows": 2, "placeholder": "Classrooms lecture, Case studies, Tutorial Classes, "
                                           "Group discussion, Seminar & field work etc.,"},
                {"name": "outcomes", "label": "Course Outcomes", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 3,
                 "placeholder": "a) Understand …\nb) Apply …\nc) …  — one per line"},
                {"name": "modules", "label": "Syllabus", "type": "module_compare", "compare": False,
                 "required": True},
                {"name": "skill_activities", "label": "Skill Development Activities", "type": "textarea",
                 "required": True, "rows": 5, "min_items": 1,
                 "placeholder": "1. …\n2. …  — one per line"},
                {"name": "books", "label": "Books for reference", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 2, "placeholder": "1. Author, Title, Publisher.  — one per line"},
            ],
            "rules": ["course_codes_known", "bloom_verbs_present"],
        },
        {
            # the syllabus as the department keeps it, beside the sheets above
            "key": "syllabus_file",
            "title": "Syllabus document",
            "type": "fields",
            "fields": [
                {"name": "document", "label": "Syllabus document (Word or PDF)", "type": "file",
                 "wide": True, "accept": ".pdf,.docx,.doc",
                 "help": "Optional. The whole syllabus as one file."},
            ],
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
        {
            "key": "revision_log",
            "title": "Course Revision Log",
            "help": "Optional: the department's own revision log workbook, if it keeps one.",
            "type": "fields",
            "fields": [
                {"name": "revision_log", "label": "Course Revision Log (Excel)", "type": "file",
                 "wide": True, "accept": ".xlsx,.xls,.pdf,.docx"},
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


def _batch_part(start: int) -> dict:
    part = _plain_syllabus(batch_key(start), f"Syllabus — Batch of {batch_label(start)}", "")
    part.update({"batch": batch_label(start), "existing_batch": True, "optional": False})
    return part


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
