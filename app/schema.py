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
               added/removed by the user
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
                {"name": "programme_count", "label": "Number of programmes offered", "type": "integer",
                 "required": True, "min": 1, "max": 100,
                 "help": "You will enter each of these programmes in the Programme Information stage."},
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
# Stage 4 — UGC Mandatory Disclosure : Programme Information
# --------------------------------------------------------------------------

PROGRAMME_INFORMATION = {
    "key": "ugc_programme",
    "group": "UGC Mandatory Disclosure",
    "title": "Programme Information",
    "blurb": "One record per programme. Section A of the Curriculum Matrix template.",
    "source_templates": ["Curriculum Matrix Template.docx (Section A)"],
    "sections": [
        {
            "key": "programmes",
            "title": "Programmes offered",
            "help": "Section A — programme profile. Every programme entered here gets its own "
                    "credit structure in the next stage.",
            "type": "table",
            "min_rows": 1,
            "programme_source": True,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "programme_name", "label": "Programme name", "type": "text", "required": True,
                 "help": "For example: Bachelor of Commerce (Corporate Finance)"},
                {"name": "programme_code", "label": "Programme code", "type": "text", "required": True,
                 "pattern": "^[A-Za-z0-9\\-]{2,20}$"},
                {"name": "degree_level", "label": "Degree / Duration", "type": "select", "required": True,
                 "options": DEGREE_LEVELS},
                {"name": "specialisation", "label": "Specialisation", "type": "text"},
                {"name": "duration_years", "label": "Duration (years)", "type": "integer", "required": True,
                 "min": 1, "max": 5},
                {"name": "semesters", "label": "Number of semesters", "type": "integer", "required": True,
                 "min": 2, "max": 10},
                {"name": "intake", "label": "Approved intake", "type": "integer", "required": True,
                 "min": 1, "max": 2000},
                {"name": "batch", "label": "Batch", "type": "text", "required": True,
                 "pattern": "^[0-9]{4}\\s*-\\s*[0-9]{2,4}$", "help": "For example 2027-31 or 2027-2031."},
                {"name": "regulation", "label": "Regulation / Framework", "type": "select", "required": True,
                 "options": ["NEP 2020", "CBCS", "Outcome Based Education", "Other"]},
                {"name": "exit_options", "label": "Multiple exit options offered", "type": "checkbox"},
            ],
            "rules": ["programme_duration_semesters", "programme_unique_codes"],
        },
        {
            "key": "vision",
            "title": "Vision, Mission and Outcomes",
            "help": "Follow the existing university vision/mission template. Do not paraphrase.",
            "type": "fields",
            "fields": [
                {"name": "vision", "label": "Department vision", "type": "textarea", "required": True,
                 "rows": 3, "min_words": 15},
                {"name": "mission", "label": "Department mission", "type": "textarea", "required": True,
                 "rows": 4, "min_words": 25},
                {"name": "peos", "label": "Programme Educational Objectives (PEOs)", "type": "textarea",
                 "required": True, "rows": 5, "min_items": 3,
                 "help": "One objective per line. At least three."},
                {"name": "pos", "label": "Programme Outcomes (POs)", "type": "textarea", "required": True,
                 "rows": 6, "min_items": 5, "help": "One outcome per line. At least five."},
                {"name": "psos", "label": "Programme Specific Outcomes (PSOs)", "type": "textarea",
                 "required": True, "rows": 4, "min_items": 2,
                 "help": "One outcome per line. At least two."},
            ],
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
    "blurb": "Credit distribution per programme, checked live against UGC Table 2 "
             "(Minimum Credit Requirements to Award Degree under Each Category).",
    "source_templates": [
        "Curriculum Matrix Template.docx (Sections B, C, D)",
        "BCom (Corporate Finance) Honours / Honours with Research V1 25 Jun.docx",
    ],
    "per_programme": True,
    "sections": [
        {
            "key": "credit_summary",
            "title": "Section B — Credit classification",
            "help": "Enter the credits your programme awards in each UGC category. "
                    "The minimum column is fixed by UGC Table 2 and cannot be edited.",
            "type": "credit_matrix",
            "rules": ["ugc_table2_minimums", "ugc_total_credits", "ugc_research_or_lieu"],
        },
        {
            "key": "semester_structure",
            "title": "Section C — Semester-wise programme structure",
            "help": "One row per course, for every semester of the programme.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "semester", "label": "Semester", "type": "integer", "required": True,
                 "min": 1, "max": 10, "width": "90px"},
                {"name": "course_code", "label": "Course code", "type": "text", "required": True,
                 "pattern": "^[A-Z]{2,4}[0-9]{0,2}\\.[0-9]{1,2}\\.[0-9]{1,2}$",
                 "help": "Format: letters, then section numbers. Example COM.5.1"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True,
                 "pattern": "^[A-Za-z0-9 ,.:()&'\\-/]{3,120}$"},
                {"name": "nep_category", "label": "NEP category", "type": "select", "required": True,
                 "options": NEP_CATEGORIES},
                {"name": "l", "label": "L", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "60px", "help": "Lecture hours"},
                {"name": "t", "label": "T", "type": "integer", "required": True, "min": 0, "max": 10,
                 "width": "60px", "help": "Tutorial hours"},
                {"name": "p", "label": "P", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "60px", "help": "Practical hours"},
                {"name": "e", "label": "E", "type": "integer", "required": True, "min": 0, "max": 20,
                 "width": "60px", "help": "Experiential hours"},
                {"name": "credits", "label": "Credits", "type": "integer", "required": True,
                 "min": 1, "max": 20, "width": "80px"},
                {"name": "cia", "label": "CIA marks", "type": "integer", "required": True,
                 "min": 0, "max": 500, "width": "90px"},
                {"name": "ese", "label": "ESE marks", "type": "integer", "required": True,
                 "min": 0, "max": 500, "width": "90px"},
                {"name": "total_marks", "label": "Total marks", "type": "integer", "required": True,
                 "min": 0, "max": 1000, "width": "100px"},
            ],
            "rules": [
                "ltpe_credit_arithmetic",
                "credit_marks_ratio",
                "marks_add_up",
                "semester_within_duration",
                "unique_course_codes",
                "category_totals_match_summary",
            ],
        },
        {
            "key": "regulations",
            "title": "Section D — Regulations and exit options",
            "type": "fields",
            "fields": [
                {"name": "framework", "label": "Curriculum framework", "type": "select", "required": True,
                 "options": ["NEP 2020", "CBCS", "Other"]},
                {"name": "min_pass_percent", "label": "Minimum pass percentage", "type": "integer",
                 "required": True, "min": 30, "max": 60},
                {"name": "attendance_percent", "label": "Minimum attendance percentage", "type": "integer",
                 "required": True, "min": 50, "max": 100},
                {"name": "exit_cert", "label": "Certificate exit after year 1 (credits)", "type": "integer",
                 "min": 0, "max": 60},
                {"name": "exit_diploma", "label": "Diploma exit after year 2 (credits)", "type": "integer",
                 "min": 0, "max": 100},
                {"name": "minor_offered", "label": "Minor stream offered", "type": "checkbox"},
                {"name": "honours_research", "label": "Honours with Research track offered", "type": "checkbox"},
                {"name": "elective_basket", "label": "Elective basket description", "type": "textarea", "rows": 3},
            ],
        },
        {
            "key": "minors",
            "title": "Annexure I — Minor subjects offered",
            "type": "table",
            "min_rows": 0,
            "columns": [
                {"name": "sl", "label": "S. No.", "type": "integer", "width": "70px", "auto_index": True},
                {"name": "minor_title", "label": "Minor subject", "type": "text", "required": True},
                {"name": "offered_by", "label": "Offered by department", "type": "text", "required": True},
                {"name": "credits", "label": "Total credits", "type": "integer", "required": True,
                 "min": 1, "max": 60},
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
    "blurb": "The syllabus record for each course, with course outcomes and CO-PO mapping.",
    "source_templates": ["[Template] Syllabus.pdf (with skill mapping requirement)"],
    "per_programme": True,
    "sections": [
        {
            "key": "courses",
            "title": "Syllabus",
            "help": "Course codes are drawn from the programme structure you submitted in the "
                    "previous stage. Add the syllabus detail for each.",
            "type": "table",
            "min_rows": 1,
            "columns": [
                {"name": "course_code", "label": "Course code", "type": "text", "required": True,
                 "from_previous": "ugc_curriculum.semester_structure.course_code"},
                {"name": "course_title", "label": "Course title", "type": "text", "required": True},
                {"name": "course_type", "label": "Course type", "type": "select", "required": True,
                 "options": COURSE_TYPES},
                {"name": "objectives", "label": "Course objectives", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2, "help": "One objective per line, at least two."},
                {"name": "outcomes", "label": "Course outcomes (COs)", "type": "textarea", "required": True,
                 "rows": 4, "min_items": 4,
                 "help": "One outcome per line, at least four. Begin each with a Bloom's taxonomy action verb."},
                {"name": "units", "label": "Units / Modules", "type": "textarea", "required": True,
                 "rows": 5, "min_items": 4, "help": "One unit per line, at least four."},
                {"name": "skill_mapping", "label": "Skill mapping", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 1,
                 "help": "Mandatory. Map each unit to the skill it builds."},
                {"name": "co_po_map", "label": "CO-PO mapping", "type": "textarea", "required": True,
                 "rows": 3, "help": "For example: CO1-PO1(3), CO1-PO3(2), CO2-PO2(3)",
                 "pattern": "^(CO[0-9]+\\s*-\\s*(PO|PSO)[0-9]+\\s*\\([123]\\)\\s*,?\\s*)+$"},
                {"name": "textbooks", "label": "Text books", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2},
                {"name": "references", "label": "Reference books", "type": "textarea", "required": True,
                 "rows": 3, "min_items": 2},
                {"name": "resources", "label": "Learning resources", "type": "textarea", "rows": 2},
                {"name": "assessment", "label": "Assessment pattern", "type": "textarea", "required": True,
                 "rows": 2},
                {"name": "question_paper", "label": "Sample question paper", "type": "file",
                 "accept": ".pdf,.docx"},
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
    "group": "Approval",
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
