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
# Stage 1 — Department Information
# --------------------------------------------------------------------------

DEPARTMENT_INFORMATION = {
    "key": "dept_info",
    "group": "Department",
    "title": "Department Information",
    "blurb": "Confirm the department record the Office of Academics holds for you. "
             "Correct anything that is out of date before you move on.",
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
                    "new programme. This list carries into the UGC Mandatory Disclosure stages.",
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
# Stage 2 — Pre-BoS  (the three composition templates)
# --------------------------------------------------------------------------

PRE_BOS = {
    "key": "pre_bos",
    "group": "Pre-BoS",
    "title": "Pre-BoS",
    "blurb": "Upload the three signed composition documents. Nothing else opens until "
             "this stage is submitted.",
    "source_templates": [
        "[Template] Composition of DIAC.docx",
        "[Template] Composition of the Board of Studies - Template.docx",
        "[Template] Composition of the Program Assessment Committee Template.docx",
    ],
    "sections": [
        {
            "key": "pre_bos_files",
            "title": "Signed composition documents",
            "help": "Fill the three university templates offline, have them signed, and upload "
                    "them here as PDF or Word files. Use the template names above so the Office "
                    "of Academics can match them.",
            "type": "fields",
            "fields": [
                {"name": "diac_signed",
                 "label": "Composition of the Department Industry-Academia Cell (DIAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "help": "Signed copy of [Template] Composition of DIAC.docx"},
                {"name": "bos_signed",
                 "label": "Composition of the Board of Studies",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "help": "Signed copy of [Template] Composition of the Board of Studies."},
                {"name": "pac_signed",
                 "label": "Composition of the Programme Assessment Committee (PAC)",
                 "type": "file", "required": True, "wide": True, "accept": ".pdf,.docx,.doc",
                 "help": "Signed copy of [Template] Composition of the Program Assessment "
                         "Committee."},
            ],
        },
        {
            "key": "pre_bos_extra",
            "title": "Anything else (optional)",
            "type": "fields",
            "fields": [
                {"name": "nomination_letters", "label": "Nomination letters", "type": "file",
                 "accept": ".pdf,.docx,.doc", "wide": True,
                 "help": "Optional. Nomination or appointment letters for external members."},
                {"name": "notes", "label": "Note to the Office of Academics", "type": "textarea",
                 "rows": 3, "wide": True,
                 "help": "Optional. Anything the Office should know about these documents."},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 3 — BoS Committee Information / Expert Profile
# --------------------------------------------------------------------------

BOS_COMMITTEE = {
    "key": "bos_committee",
    "group": "Pre-BoS",
    "title": "BoS Committee Information",
    "blurb": "Expert profiles for every external member named in the Board of Studies.",
    "source_templates": ["Expert Profile_Form.docx"],
    "sections": [
        {
            "key": "experts",
            "title": "Expert profile",
            "help": "From Expert Profile_Form.docx. One row per external academic, industry expert "
                    "and alumni representative listed in your Board of Studies.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "name", "label": "Name", "type": "text", "required": True,
                 "pattern": "^[A-Za-z .'\\-]{3,80}$"},
                {"name": "category", "label": "Category", "type": "select", "required": True,
                 "options": ["External Expert - Academia", "External Expert - Industry",
                             "Alumni Representative", "Student Representative"]},
                {"name": "designation", "label": "Designation", "type": "text", "required": True},
                {"name": "organisation", "label": "Institution / Company", "type": "text", "required": True},
                {"name": "qualification", "label": "Highest qualification", "type": "text", "required": True},
                {"name": "experience_years", "label": "Experience (years)", "type": "integer",
                 "required": True, "min": 0, "max": 60},
                {"name": "specialisation", "label": "Area of specialisation", "type": "text", "required": True},
                {"name": "email", "label": "Email address", "type": "email", "required": True},
                {"name": "phone", "label": "Mobile number", "type": "phone", "pattern": "^[0-9+ ]{10,15}$"},
                {"name": "consent", "label": "Consent received", "type": "checkbox", "required": True},
                {"name": "cv", "label": "Profile / CV", "type": "file", "accept": ".pdf,.docx"},
            ],
            "rules": ["experts_unique_emails"],
        },
    ],
}


# --------------------------------------------------------------------------
# UGC Mandatory Disclosure — laid out as the Office of Academics' three
# columns: Programme Information | Curriculum & Regulations | Course
# Information. The fields follow the Curriculum Matrix template, and the
# default wording is the university-wide text of the BCom (Corporate
# Finance) sample built on it.
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
# Stage 4 — UGC Mandatory Disclosure : Programme Information
# --------------------------------------------------------------------------

PROGRAMME_INFORMATION = {
    "key": "ugc_programme",
    "group": "UGC Mandatory Disclosure",
    "title": "Programme Information",
    "blurb": "One record per programme: name, code, degree, specialisation, intake, duration, "
             "credits, batch and NEP category.",
    "source_templates": ["Curriculum Matrix Template.docx"],
    "sections": [
        {
            "key": "programmes",
            "title": "Programmes offered",
            "help": "Every programme here gets its own curriculum and course information in "
                    "the next two stages.",
            "type": "table",
            "min_rows": 1,
            "programme_source": True,
            # rows come from Department Information → Programmes offered;
            # code and name are fixed here, the rest is filled per programme
            "synced_from": "dept_info",
            # one framed card per programme rather than a wide table row
            "display": "cards",
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "programme_name", "label": "Programme name", "type": "text", "required": True,
                 "help": "For example: Bachelor of Commerce (Corporate Finance)"},
                {"name": "programme_code", "label": "Programme code", "type": "text", "required": True,
                 "pattern": "^[A-Za-z0-9\\-]{2,20}$"},
                {"name": "degree_level", "label": "Degree", "type": "select", "required": True,
                 "options": DEGREE_LEVELS},
                {"name": "specialisation", "label": "Specialisation", "type": "text"},
                {"name": "intake", "label": "Intake", "type": "integer", "required": True,
                 "min": 1, "max": 2000},
                {"name": "duration_years", "label": "Duration (years)", "type": "integer",
                 "required": True, "min": 1, "max": 5},
                {"name": "total_credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 1, "max": 400,
                 "help": "Total credits to award the degree. At least 120 for a 3-year UG and "
                         "160 for a 4-year UG under UGC Table 2."},
                {"name": "batch", "label": "Batch", "type": "text", "required": True,
                 "pattern": "^[0-9]{4}\\s*-\\s*[0-9]{2,4}$", "help": "For example 2026-30."},
                {"name": "regulation", "label": "NEP category", "type": "select", "required": True,
                 "options": NEP_FRAMEWORKS},
            ],
            "rules": ["programme_duration_semesters", "programme_unique_codes"],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 5 — UGC Mandatory Disclosure : Curriculum & Regulations
#           (this is where the UGC Table 2 credit engine runs)
# --------------------------------------------------------------------------

CURRICULUM_REGULATIONS = {
    "key": "ugc_curriculum",
    "group": "UGC Mandatory Disclosure",
    "title": "Curriculum & Regulations",
    "blurb": "The programme structure semester by semester, its credit distribution checked "
             "against UGC Table 2, and the regulations that govern it.",
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
            "title": "Credit distribution — classification of credits",
            "help": "Worked out from the programme structure above, in the layout of the "
                    "template: credits per semester in each group, the summary of "
                    "continuous-assessment and term-end credits, and the check against UGC "
                    "Table 2. Nothing to type here.",
            "type": "credit_distribution",
            "rules": ["ugc_table2_minimums", "ugc_total_credits"],
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
                {"name": "reservation_policy", "label": "4. Reservation", "type": "textarea",
                 "required": True, "rows": 2, "wide": True,
                 "prefill_text": DEFAULT_REGULATIONS["reservation_policy"],
                 "help": "Within the sanctioned intake: SC, ST, differently abled and defence "
                         "(in percentage). Over and above: Kashmiri migrants (in seats) and "
                         "international students (in percentage)."},
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
            "key": "regulations",
            "title": "CBCS / NEP framework, exit options and elective basket",
            "type": "fields",
            "fields": [
                {"name": "framework", "label": "CBCS / NEP framework", "type": "select",
                 "required": True, "options": ["NEP 2020", "CBCS", "Other"]},
                {"name": "exit_cert", "label": "Exit with UG Certificate after year 1 (credits)",
                 "type": "integer", "min": 0, "max": 60},
                {"name": "exit_diploma", "label": "Exit with UG Diploma after year 2 (credits)",
                 "type": "integer", "min": 0, "max": 100},
                {"name": "elective_basket", "label": "Elective basket", "type": "textarea",
                 "rows": 3, "wide": True,
                 "help": "The electives students choose from, and how many they take."},
            ],
            "links": [{"label": "Design and Development plan", "stage": "dd_plan"}],
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
    ],
}


# --------------------------------------------------------------------------
# Stage 6 — UGC Mandatory Disclosure : Course Information (syllabus)
# --------------------------------------------------------------------------

COURSE_INFORMATION = {
    "key": "ugc_course",
    "group": "UGC Mandatory Disclosure",
    "title": "Course Information",
    "blurb": "The syllabus record for each course: objectives, outcomes, CO-PO mapping, "
             "assessment, units and books.",
    "source_templates": ["[Template] Syllabus.pdf"],
    "per_programme": True,
    "sections": [
        {
            "key": "courses",
            "title": "Courses",
            "help": "Every course in the programme structure gets a card. Code, title, credits "
                    "and L-T-P-E come from the Curriculum & Regulations stage.",
            "type": "table",
            "min_rows": 1,
            "display": "cards",
            "card": {"code": "course_code", "name": "course_title", "noun": "course"},
            "tabs": [{"key": "details", "label": "Course details"},
                     {"key": "syllabus", "label": "Syllabus & books"}],
            "columns": [
                {"name": "course_code", "label": "Course code", "type": "text", "required": True,
                 "from_previous": "ugc_curriculum.semester_structure.course_code"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 0, "max": 20},
                {"name": "ltpe", "label": "L-T-P-E structure", "type": "text", "required": True,
                 "pattern": "^[0-9]{1,2}-[0-9]{1,2}-[0-9]{1,2}-[0-9]{1,2}$",
                 "help": "For example 3-1-0-0."},
                {"name": "objectives", "label": "Course objectives", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2, "help": "One objective per line, at least two."},
                {"name": "outcomes", "label": "Course outcomes (COs)", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 4,
                 "help": "One outcome per line, at least four. Begin each with a Bloom's taxonomy action verb."},
                {"name": "co_po_map", "label": "CO-PO mapping", "type": "textarea", "required": True,
                 "rows": 3, "help": "For example: CO1-PO1(3), CO1-PO3(2), CO2-PO2(3)",
                 "pattern": "^(CO[0-9]+\\s*-\\s*(PO|PSO)[0-9]+\\s*\\([123]\\)\\s*,?\\s*)+$"},
                {"name": "assessment", "label": "Assessment pattern", "type": "textarea", "required": True,
                 "rows": 2, "help": "For example: CA 50 (two tests, assignment, quiz) and ESE 50."},
                {"name": "units", "label": "Syllabus — units / modules", "type": "textarea",
                 "required": True, "rows": 6, "min_items": 4, "tab": "syllabus",
                 "help": "One unit per line, at least four."},
                {"name": "textbooks", "label": "Text books", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2, "tab": "syllabus"},
                {"name": "references", "label": "Reference books", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2, "tab": "syllabus"},
                {"name": "resources", "label": "Learning resources", "type": "textarea", "rows": 2,
                 "tab": "syllabus"},
            ],
            "rules": ["course_codes_known", "bloom_verbs_present", "co_po_wellformed"],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 7 — Course Revision & Mapping
# --------------------------------------------------------------------------

COURSE_REVISION = {
    "key": "course_revision",
    "group": "Revision",
    "title": "Course Revision & Mapping",
    "blurb": "What changed since the last approved version, and why.",
    "source_templates": ["Course Revisions Log_Template_2026.xlsx", "CR Blank Template"],
    "per_programme": True,
    "sections": [
        {
            "key": "revision_log",
            "title": "Course revision log",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "existing_code", "label": "Existing course code", "type": "text", "required": True},
                {"name": "existing_title", "label": "Existing course title", "type": "text", "required": True},
                {"name": "existing_credits", "label": "Existing credits", "type": "integer",
                 "required": True, "min": 0, "max": 20},
                {"name": "revised_code", "label": "Revised course code", "type": "text", "required": True},
                {"name": "revised_title", "label": "Revised course title", "type": "text", "required": True},
                {"name": "revised_credits", "label": "Revised credits", "type": "integer",
                 "required": True, "min": 0, "max": 20},
                {"name": "change_type", "label": "Nature of change", "type": "select", "required": True,
                 "options": ["Title changed", "Content revised", "Credits changed", "Category changed",
                             "New course", "Course withdrawn", "Merged", "Split"]},
                {"name": "percent_changed", "label": "% content changed", "type": "integer",
                 "required": True, "min": 0, "max": 100},
                {"name": "justification", "label": "Justification", "type": "textarea", "required": True,
                 "rows": 2, "min_words": 10},
                {"name": "benchmark", "label": "Benchmarked against", "type": "text", "required": True,
                 "help": "Name the institution or framework the revision was benchmarked against."},
            ],
            "rules": ["revision_change_needs_justification", "revision_percent_threshold"],
        },
        {
            "key": "gap_analysis",
            "title": "Gap analysis and industry inputs",
            "type": "fields",
            "fields": [
                {"name": "gap_summary", "label": "Gap analysis summary", "type": "textarea",
                 "required": True, "rows": 4, "min_words": 40},
                {"name": "industry_inputs", "label": "Industry inputs incorporated", "type": "textarea",
                 "required": True, "rows": 4, "min_words": 30},
                {"name": "version_number", "label": "Curriculum version number", "type": "text",
                 "required": True, "pattern": "^[Vv]?[0-9]+(\\.[0-9]+)?$", "help": "For example V1 or V2.1"},
                {"name": "revision_log_file", "label": "Signed revision log", "type": "file",
                 "accept": ".pdf,.xlsx,.docx"},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 8 — Stakeholder Feedback
# --------------------------------------------------------------------------

STAKEHOLDER_FEEDBACK = {
    "key": "stakeholder",
    "group": "Evidence",
    "title": "Stakeholder Feedback",
    "blurb": "Feedback collected from every stakeholder group, and what you did about it.",
    "source_templates": ["Stakeholder Input Log for Curriculum Design and Development"],
    "sections": [
        {
            "key": "input_log",
            "title": "Stakeholder input log",
            "help": "All six stakeholder groups must appear at least once: "
                    "Faculty, Student, Alumni, Employer, Industry, Academic Peer.",
            "type": "table",
            "min_rows": 6,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "source", "label": "Stakeholder group", "type": "select", "required": True,
                 "options": FEEDBACK_SOURCES},
                {"name": "respondent", "label": "Respondent name / group", "type": "text", "required": True},
                {"name": "collected_on", "label": "Collected on", "type": "date", "required": True},
                {"name": "mode", "label": "Mode", "type": "select", "required": True,
                 "options": ["Survey", "Interview", "Focus group", "Written note", "Meeting"]},
                {"name": "respondents_count", "label": "Number of respondents", "type": "integer",
                 "required": True, "min": 1, "max": 10000},
                {"name": "input_summary", "label": "Input received", "type": "textarea", "required": True,
                 "rows": 2, "min_words": 8},
                {"name": "action_taken", "label": "Action taken", "type": "textarea", "required": True,
                 "rows": 2, "min_words": 8},
                {"name": "evidence", "label": "Evidence", "type": "file", "accept": ".pdf,.xlsx,.docx,.png,.jpg"},
            ],
            "rules": ["all_stakeholder_groups_present", "feedback_date_within_year"],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 9 — Meeting Documents
# --------------------------------------------------------------------------

MEETING_DOCUMENTS = {
    "key": "meeting_docs",
    "group": "Evidence",
    "title": "Meeting Documents",
    "blurb": "Notice, agenda, attendance, minutes, resolutions and photographs of the BoS meeting.",
    "source_templates": ["Minutes of the Meeting_Template.docx", "Minutes of the Meeting_Sample"],
    "sections": [
        {
            "key": "meeting",
            "title": "Meeting particulars",
            "type": "fields",
            "fields": [
                {"name": "meeting_number", "label": "Meeting number", "type": "text", "required": True},
                {"name": "meeting_date", "label": "Date of the meeting", "type": "date", "required": True},
                {"name": "meeting_time", "label": "Time", "type": "text", "required": True},
                {"name": "venue", "label": "Venue", "type": "text", "required": True},
                {"name": "mode", "label": "Mode", "type": "select", "required": True,
                 "options": ["In person", "Online", "Hybrid"]},
                {"name": "notice_date", "label": "Date notice was circulated", "type": "date", "required": True,
                 "help": "Must be at least seven days before the meeting date."},
                {"name": "chairperson", "label": "Chaired by", "type": "text", "required": True},
                {"name": "members_present", "label": "Members present", "type": "integer", "required": True,
                 "min": 1, "max": 100},
                {"name": "members_absent", "label": "Members absent", "type": "integer", "required": True,
                 "min": 0, "max": 100},
            ],
            "rules": ["notice_seven_days", "quorum_met"],
        },
        {
            "key": "resolutions",
            "title": "Resolutions and action items",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "agenda_item", "label": "Agenda item", "type": "text", "required": True},
                {"name": "discussion", "label": "Discussion", "type": "textarea", "required": True,
                 "rows": 2, "min_words": 10},
                {"name": "resolution", "label": "Resolution", "type": "textarea", "required": True,
                 "rows": 2, "min_words": 8},
                {"name": "action_by", "label": "Action by", "type": "text", "required": True},
                {"name": "target_date", "label": "Target date", "type": "date", "required": True},
            ],
        },
        {
            "key": "meeting_files",
            "title": "Meeting documents",
            "type": "fields",
            "fields": [
                {"name": "notice", "label": "Notice", "type": "file", "required": True, "accept": ".pdf,.docx"},
                {"name": "agenda", "label": "Agenda", "type": "file", "required": True, "accept": ".pdf,.docx"},
                {"name": "attendance", "label": "Attendance sheet (signed)", "type": "file",
                 "required": True, "accept": ".pdf,.png,.jpg"},
                {"name": "minutes", "label": "Minutes of the meeting", "type": "file", "required": True,
                 "accept": ".pdf,.docx"},
                {"name": "presentation", "label": "Presentation", "type": "file", "accept": ".pdf,.pptx"},
                {"name": "photos", "label": "Meeting photographs", "type": "file",
                 "accept": ".png,.jpg,.jpeg,.zip", "multiple": True},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 10 — Approval & Compliance
# --------------------------------------------------------------------------

APPROVAL_COMPLIANCE = {
    "key": "approval",
    "group": "Approval",
    "title": "Approval & Compliance",
    "blurb": "The approval chain, in order. Each level needs a name, a date and a signed document.",
    "sections": [
        {
            "key": "approvals",
            "title": "Approval chain",
            "type": "table",
            "min_rows": 5,
            "fixed_rows": APPROVAL_LEVELS,
            "columns": [
                {"name": "level", "label": "Approval level", "type": "readonly", "required": True},
                {"name": "approver_name", "label": "Name of the approver", "type": "text", "required": True},
                {"name": "approved_on", "label": "Approved on", "type": "date", "required": True},
                {"name": "reference", "label": "Reference / resolution number", "type": "text", "required": True},
                {"name": "document", "label": "Signed approval", "type": "file", "required": True,
                 "accept": ".pdf"},
            ],
            "rules": ["approval_chain_order", "approval_after_meeting"],
        },
        {
            "key": "compliance",
            "title": "Compliance checklist",
            "type": "fields",
            "fields": [
                {"name": "ugc_compliant", "label": "Credit structure complies with UGC Table 2",
                 "type": "checkbox", "required": True},
                {"name": "nep_compliant", "label": "Programme complies with the NEP 2020 framework",
                 "type": "checkbox", "required": True},
                {"name": "feedback_incorporated", "label": "Stakeholder feedback has been incorporated",
                 "type": "checkbox", "required": True},
                {"name": "syllabus_complete", "label": "Syllabus with CO-PO mapping is complete for every course",
                 "type": "checkbox", "required": True},
                {"name": "version_number", "label": "Version number submitted", "type": "text", "required": True},
                {"name": "submission_date", "label": "Submission date", "type": "date", "required": True},
                {"name": "declaration", "label": "I declare that the information submitted is true and complete",
                 "type": "checkbox", "required": True},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 11 — Supporting Documents
# --------------------------------------------------------------------------

SUPPORTING_DOCUMENTS = {
    "key": "supporting",
    "group": "Approval",
    "title": "Supporting Documents",
    "blurb": "Matrices, rubrics, calendar and annexures that travel with the submission.",
    "sections": [
        {
            "key": "docs",
            "title": "Supporting documents",
            "type": "fields",
            "fields": [
                {"name": "course_matrix", "label": "Course matrix", "type": "file", "required": True,
                 "accept": ".xlsx,.pdf,.docx"},
                {"name": "programme_matrix", "label": "Programme matrix", "type": "file", "required": True,
                 "accept": ".xlsx,.pdf,.docx"},
                {"name": "mapping_matrix", "label": "CO-PO mapping matrix", "type": "file", "required": True,
                 "accept": ".xlsx,.pdf"},
                {"name": "rubrics", "label": "Assessment rubrics", "type": "file", "accept": ".pdf,.docx"},
                {"name": "academic_calendar", "label": "Academic calendar", "type": "file", "accept": ".pdf,.xlsx"},
                {"name": "question_papers", "label": "Sample question papers", "type": "file",
                 "accept": ".pdf,.zip", "multiple": True},
                {"name": "annexures", "label": "Additional annexures", "type": "file",
                 "accept": ".pdf,.docx,.xlsx,.zip", "multiple": True},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 12 — Design and Development Plan
# --------------------------------------------------------------------------

DESIGN_DEVELOPMENT_PLAN = {
    "key": "dd_plan",
    "group": "Planning",
    "title": "Design and Development Plan",
    "blurb": "The forward plan for the coming academic year, including the twelve planning items "
             "the Office of Academics tracks.",
    "source_templates": ["Design & Development Plan Sample Template"],
    "sections": [
        {
            "key": "plan_items",
            "title": "Planning items",
            "help": "The twelve items tracked by the Office of Academics. Mark each as applicable "
                    "or not, and give a target date where it applies.",
            "type": "table",
            "min_rows": 12,
            "fixed_rows": [
                "Innovative and Emerging Areas",
                "Assessment (if any) to be collected",
                "Open Electives",
                "Year end Planning of TDPCL 2027-28",
                "Mentoring 2027-28",
                "Experiential Learning",
                "Internship",
                "Course revision log - comparison",
                "AQR Documents",
                "Design and Development",
                "New Programme proposals",
                "Vision and Mission review",
            ],
            "columns": [
                {"name": "item", "label": "Planning item", "type": "readonly"},
                {"name": "applicable", "label": "Applicable", "type": "select", "required": True,
                 "options": ["Yes", "Not applicable"]},
                {"name": "owner", "label": "Owner", "type": "text"},
                {"name": "target_date", "label": "Target date", "type": "date"},
                {"name": "remarks", "label": "Remarks", "type": "textarea", "rows": 2},
            ],
            "rules": ["plan_applicable_needs_detail"],
        },
        {
            "key": "new_programmes",
            "title": "New programme proposals",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "programme_name", "label": "Proposed programme", "type": "text", "required": True},
                {"name": "degree_level", "label": "Degree / Duration", "type": "select", "required": True,
                 "options": DEGREE_LEVELS},
                {"name": "rationale", "label": "Rationale", "type": "textarea", "required": True,
                 "rows": 3, "min_words": 25},
                {"name": "demand_evidence", "label": "Evidence of demand", "type": "textarea",
                 "required": True, "rows": 2, "min_words": 15},
                {"name": "proposed_intake", "label": "Proposed intake", "type": "integer",
                 "required": True, "min": 1, "max": 2000},
                {"name": "start_year", "label": "Proposed start year", "type": "text", "required": True,
                 "pattern": "^[0-9]{4}\\s*-\\s*[0-9]{2,4}$"},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Stage 13 — Final BoS Repository
# --------------------------------------------------------------------------

FINAL_REPOSITORY = {
    "key": "final_repo",
    # Its own group: it is the sealing of the record, not another approval,
    # and labelling it "Approval" put that heading on the board twice with
    # Planning in between them.
    "group": "Repository",
    "title": "Final BoS Repository",
    "blurb": "The consolidated, signed bundle. Once submitted the whole record is sealed and "
             "only the Office of Academics can reopen it.",
    "sections": [
        {
            "key": "final",
            "title": "Consolidated submission",
            "type": "fields",
            "fields": [
                {"name": "approved_bos_file", "label": "Approved BoS file", "type": "file",
                 "required": True, "accept": ".pdf"},
                {"name": "consolidated_pdf", "label": "Consolidated PDF of all documents", "type": "file",
                 "required": True, "accept": ".pdf"},
                {"name": "digital_signatures", "label": "Digitally signed copy", "type": "file",
                 "accept": ".pdf"},
                {"name": "version_number", "label": "Final version number", "type": "text", "required": True},
                {"name": "remarks", "label": "Remarks to the Office of Academics", "type": "textarea", "rows": 3},
                {"name": "final_declaration",
                 "label": "I confirm this is the final, approved Board of Studies record for the academic year",
                 "type": "checkbox", "required": True},
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Ordered stage list  — this order IS the lock order
# --------------------------------------------------------------------------

STAGES = [
    DEPARTMENT_INFORMATION,
    PRE_BOS,
    BOS_COMMITTEE,
    PROGRAMME_INFORMATION,
    CURRICULUM_REGULATIONS,
    COURSE_INFORMATION,
    COURSE_REVISION,
    STAKEHOLDER_FEEDBACK,
    MEETING_DOCUMENTS,
    APPROVAL_COMPLIANCE,
    SUPPORTING_DOCUMENTS,
    DESIGN_DEVELOPMENT_PLAN,
    FINAL_REPOSITORY,
]

STAGE_KEYS = [s["key"] for s in STAGES]
STAGE_BY_KEY = {s["key"]: s for s in STAGES}

GROUP_ORDER = ["Department", "Pre-BoS", "UGC Mandatory Disclosure", "Revision",
               "Evidence", "Approval", "Planning"]


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
