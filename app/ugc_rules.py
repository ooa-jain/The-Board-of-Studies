"""
UGC Table 2 — Minimum Credit Requirements to Award Degree under Each Category.

Transcribed from the UGC curriculum framework table supplied by the Office of
Academics.  These values are the seed; an administrator can edit them in
Admin > Rule Configuration and the stored copy then takes precedence.

    S.No  Broad Category of Course                    3-year UG   4-Year UG
    1     Major (Core)                                   60          80
    2     Minor Stream                                   24          32
    3     Multidisciplinary                              09          09
    4     Ability Enhancement Courses (AEC)              08          08
    5     Skill Enhancement Courses (SEC)                09          09
    6     Value Added Courses common for all UG          06 - 08     06 - 08
    7     Summer Internship                              02 - 04     02 - 04
    8     Research Project / Dissertation                 -          12
          Total                                         120         160

    Note: Honours students not undertaking research will do 3 courses for
    12 credits in lieu of a research project / dissertation.
"""

TRACK_3YR = "ug3"
TRACK_4YR = "ug4"

TRACKS = {
    TRACK_3YR: "3-year UG",
    TRACK_4YR: "4-Year UG",
}

# Map the degree/duration choices offered in the Programme Information stage
# onto a UGC track.
DEGREE_TO_TRACK = {
    "UG - 3 Year": TRACK_3YR,
    "UG - 4 Year (Honours)": TRACK_4YR,
    "UG - 4 Year (Honours with Research)": TRACK_4YR,
}

HONOURS_WITH_RESEARCH = "UG - 4 Year (Honours with Research)"
HONOURS_NO_RESEARCH = "UG - 4 Year (Honours)"

# ---------------------------------------------------------------------------
# The table itself.  `min` is the floor; `max` is set only where the UGC table
# prints a range.  `applicable = False` means the category does not apply to
# that track at all (the dash in the printed table).
# ---------------------------------------------------------------------------

DEFAULT_TABLE_2 = [
    {
        "sl": 1, "key": "major_core", "label": "Major (Core)",
        "ug3": {"min": 60, "max": None, "applicable": True},
        "ug4": {"min": 80, "max": None, "applicable": True},
    },
    {
        "sl": 2, "key": "minor_stream", "label": "Minor Stream",
        "ug3": {"min": 24, "max": None, "applicable": True},
        "ug4": {"min": 32, "max": None, "applicable": True},
    },
    {
        "sl": 3, "key": "multidisciplinary", "label": "Multidisciplinary",
        "ug3": {"min": 9, "max": None, "applicable": True},
        "ug4": {"min": 9, "max": None, "applicable": True},
    },
    {
        "sl": 4, "key": "aec", "label": "Ability Enhancement Courses (AEC)",
        "ug3": {"min": 8, "max": None, "applicable": True},
        "ug4": {"min": 8, "max": None, "applicable": True},
    },
    {
        "sl": 5, "key": "sec", "label": "Skill Enhancement Courses (SEC)",
        "ug3": {"min": 9, "max": None, "applicable": True},
        "ug4": {"min": 9, "max": None, "applicable": True},
    },
    {
        "sl": 6, "key": "vac", "label": "Value Added Courses common for all UG",
        "ug3": {"min": 6, "max": 8, "applicable": True},
        "ug4": {"min": 6, "max": 8, "applicable": True},
    },
    {
        "sl": 7, "key": "internship", "label": "Summer Internship",
        "ug3": {"min": 2, "max": 4, "applicable": True},
        "ug4": {"min": 2, "max": 4, "applicable": True},
    },
    {
        "sl": 8, "key": "research", "label": "Research Project / Dissertation",
        "ug3": {"min": 0, "max": 0, "applicable": False},
        "ug4": {"min": 12, "max": None, "applicable": True},
    },
]

DEFAULT_TOTALS = {"ug3": 120, "ug4": 160}

# Honours students not undertaking research do 3 courses for 12 credits in lieu.
IN_LIEU_RULE = {
    "applies_to": HONOURS_NO_RESEARCH,
    "courses": 3,
    "credits": 12,
    "note": "Honours students not undertaking research will do 3 courses for 12 credits "
            "in lieu of a research project / dissertation.",
}

# The NEP category names used in the programme-structure grid, mapped onto the
# UGC Table 2 category keys.
NEP_CATEGORY_TO_KEY = {
    "Major (Core)": "major_core",
    "Minor Stream": "minor_stream",
    "Multidisciplinary": "multidisciplinary",
    "Ability Enhancement Courses (AEC)": "aec",
    "Skill Enhancement Courses (SEC)": "sec",
    "Value Added Courses (VAC)": "vac",
    "Summer Internship": "internship",
    "Research Project / Dissertation": "research",
}

# ---------------------------------------------------------------------------
# Other rules the Office of Academics enforces alongside Table 2
# ---------------------------------------------------------------------------

DEFAULT_OTHER_RULES = {
    # 1 credit carries 25 marks of assessment weight.
    "marks_per_credit": 25,
    # Credit arithmetic from contact hours: 1 credit per lecture or tutorial hour,
    # 1 credit per 2 practical or experiential hours.
    "credit_from_hours": {"lecture": 1.0, "tutorial": 1.0, "practical": 0.5, "experiential": 0.5},
    "credit_arithmetic_tolerance": 0.5,
    # A course may not exceed this many credits.
    "max_credits_per_course": 8,
    # Notice for a BoS meeting must go out at least this many days ahead.
    "meeting_notice_days": 7,
    # Quorum for a Board of Studies meeting.
    "quorum_fraction": 0.5,
    # A course revision above this percentage needs benchmarking evidence.
    "revision_benchmark_threshold": 30,
    # Minimum Board of Studies composition.
    "bos_min": {
        "Internal Member - Faculty": 2,
        "External Expert - Academia": 1,
        "External Expert - Industry": 1,
        "Alumni Representative": 1,
    },
}


def get_track(degree_level: str):
    """Return 'ug3' / 'ug4' for a degree choice, or None for PG."""
    return DEGREE_TO_TRACK.get(degree_level)


def table_for_track(table, track):
    """Return [(row, spec)] for the rows that apply to a track."""
    out = []
    for row in table:
        spec = row.get(track) or {}
        out.append((row, spec))
    return out


def blank_credit_matrix(table, track, degree_level=None):
    """A ready-to-render credit matrix for a given track."""
    rows = []
    for row in table:
        spec = row.get(track, {})
        applicable = bool(spec.get("applicable"))
        if (row["key"] == "research" and degree_level == HONOURS_NO_RESEARCH):
            applicable = False
        rows.append({
            "key": row["key"],
            "sl": row["sl"],
            "label": row["label"],
            "min": spec.get("min", 0),
            "max": spec.get("max"),
            "applicable": applicable,
            "credits": None,
        })
    return rows
