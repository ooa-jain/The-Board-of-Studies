"""The credit engine, checked against the printed UGC Table 2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ugc_rules as U
from app.validation import validate_stage


def ctx(degree, semesters=8):
    return {
        "degree_level": degree,
        "track": U.get_track(degree),
        "semesters": semesters,
        "table2": U.DEFAULT_TABLE_2,
        "totals": U.DEFAULT_TOTALS,
        "prior": {},
    }


def errors(issues):
    return [i["message"] for i in issues if i["level"] == "error"]


# --------------------------------------------------------------------------
# the table itself
# --------------------------------------------------------------------------

def test_table_matches_the_printed_document():
    got = {r["key"]: (r["ug3"], r["ug4"]) for r in U.DEFAULT_TABLE_2}
    assert got["major_core"][0]["min"] == 60 and got["major_core"][1]["min"] == 80
    assert got["minor_stream"][0]["min"] == 24 and got["minor_stream"][1]["min"] == 32
    assert got["multidisciplinary"][0]["min"] == 9 and got["multidisciplinary"][1]["min"] == 9
    assert got["aec"][0]["min"] == 8 and got["aec"][1]["min"] == 8
    assert got["sec"][0]["min"] == 9 and got["sec"][1]["min"] == 9
    assert (got["vac"][0]["min"], got["vac"][0]["max"]) == (6, 8)
    assert (got["internship"][0]["min"], got["internship"][0]["max"]) == (2, 4)
    assert got["research"][0]["applicable"] is False
    assert got["research"][1]["min"] == 12
    assert U.DEFAULT_TOTALS == {"ug3": 120, "ug4": 160}


def test_degree_maps_to_the_right_column():
    assert U.get_track("UG - 3 Year") == "ug3"
    assert U.get_track("UG - 4 Year (Honours)") == "ug4"
    assert U.get_track("UG - 4 Year (Honours with Research)") == "ug4"
    assert U.get_track("PG - 2 Year") is None


# --------------------------------------------------------------------------
# minimums
# --------------------------------------------------------------------------

def _matrix(**kw):
    base = {"major_core": 60, "minor_stream": 24, "multidisciplinary": 9,
            "aec": 8, "sec": 9, "vac": 8, "internship": 2}
    base.update(kw)
    return {"credit_summary": base}


def test_a_clean_three_year_structure_passes_the_minimums():
    data = _matrix()
    data["credit_summary"]["major_core"] = 68  # to reach 120
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    msgs = errors(issues)
    assert not any("below the UGC minimum" in m for m in msgs), msgs


def test_major_below_sixty_is_rejected_for_three_year():
    data = _matrix(major_core=58)
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("Major (Core)" in m and "below the UGC minimum of 60" in m for m in errors(issues))


def test_major_below_eighty_is_rejected_for_four_year():
    data = _matrix(major_core=79, minor_stream=32, research=12)
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 4 Year (Honours with Research)"))
    assert any("below the UGC minimum of 80" in m for m in errors(issues))


def test_value_added_courses_respect_the_six_to_eight_range():
    issues, _ = validate_stage("prog_curriculum", _matrix(vac=9), ctx("UG - 3 Year", 6))
    assert any("the UGC range is 6 to 8" in m for m in errors(issues))

    issues, _ = validate_stage("prog_curriculum", _matrix(vac=5), ctx("UG - 3 Year", 6))
    assert any("Value Added" in m and "below the UGC minimum" in m for m in errors(issues))


def test_internship_respects_the_two_to_four_range():
    issues, _ = validate_stage("prog_curriculum", _matrix(internship=5), ctx("UG - 3 Year", 6))
    assert any("Summer Internship" in m and "range is 2 to 4" in m for m in errors(issues))


def test_research_does_not_apply_to_a_three_year_programme():
    issues, _ = validate_stage("prog_curriculum", _matrix(research=12), ctx("UG - 3 Year", 6))
    assert any("does not apply to a 3-year UG programme" in m for m in errors(issues))


# --------------------------------------------------------------------------
# totals and the in-lieu rule
# --------------------------------------------------------------------------

def test_the_printed_minimums_add_up_to_the_printed_total():
    """60+24+9+8+9+6..8+2..4 reaches 120; the 4-year column reaches 160."""
    issues, _ = validate_stage("prog_curriculum", _matrix(), ctx("UG - 3 Year", 6))
    assert not any("short by" in m for m in errors(issues))

    four = _matrix(major_core=80, minor_stream=32, research=12)
    issues, _ = validate_stage("prog_curriculum", four,
                               ctx("UG - 4 Year (Honours with Research)"))
    assert not any("short by" in m for m in errors(issues))


def test_total_shortfall_is_reported_with_the_gap():
    issues, _ = validate_stage("prog_curriculum", _matrix(major_core=50),
                               ctx("UG - 3 Year", 6))
    msgs = errors(issues)
    assert any("short by 10" in m for m in msgs), msgs


def test_four_year_needs_one_hundred_and_sixty():
    data = _matrix(major_core=78, minor_stream=32, research=12)
    issues, _ = validate_stage("prog_curriculum", data,
                               ctx("UG - 4 Year (Honours with Research)"))
    msgs = errors(issues)
    assert any("at least 160 credits" in m for m in msgs), msgs


def test_honours_without_research_passes_when_in_lieu_is_declared():
    data = _matrix(major_core=113, minor_stream=32)
    data["credit_summary"]["in_lieu_courses"] = 3
    data["credit_summary"]["in_lieu_credits"] = 12
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 4 Year (Honours)"))
    msgs = errors(issues)
    assert not any("in lieu" in m for m in msgs), msgs
    assert not any("short by" in m for m in msgs), msgs


# --------------------------------------------------------------------------
# course-level arithmetic
# --------------------------------------------------------------------------

def _course(**kw):
    base = {"semester": 1, "course_code": "COM.1.1", "course_title": "Financial Accounting",
            "nep_category": "Major (Core)", "l": 4, "t": 0, "p": 0, "e": 0,
            "credits": 4, "cia": 50, "ese": 50, "total_marks": 100}
    base.update(kw)
    return base


def test_ltpe_must_reconcile_with_credits():
    data = {"credit_summary": {}, "semester_structure": [_course(l=3, credits=4)]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("works out to 3 credits" in m for m in errors(issues))


def test_practical_hours_count_half():
    data = {"credit_summary": {}, "semester_structure": [_course(l=2, p=4, credits=4)]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert not any("works out to" in m for m in errors(issues))


def test_one_credit_is_twenty_five_marks_is_advice_not_a_refusal():
    """The university's own sample gives 3-credit courses 100 marks, so the
    1 credit = 25 marks guideline warns rather than blocks."""
    data = {"credit_summary": {}, "semester_structure": [_course(credits=4, total_marks=150,
                                                                 cia=75, ese=75)]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("usually carry 100 marks" in i["message"] for i in issues
               if i["level"] == "warning")
    assert not any("marks" in m and "credit" in m for m in errors(issues))


def test_cia_plus_ese_must_equal_the_total():
    data = {"credit_summary": {}, "semester_structure": [_course(cia=40, ese=50)]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("does not match the total" in m for m in errors(issues))


def test_semester_outside_the_programme_is_rejected():
    data = {"credit_summary": {}, "semester_structure": [_course(semester=8)]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("outside this programme" in m for m in errors(issues))


def test_duplicate_course_codes_are_caught():
    data = {"credit_summary": {}, "semester_structure": [_course(), _course()]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("is used twice" in m for m in errors(issues))


def test_malformed_course_code_is_caught():
    # codes look like 26BCC1C01; punctuation at the start is not a code
    data = {"credit_summary": {}, "semester_structure": [_course(course_code="#bad code!")]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert any("Course code" in m and "expected format" in m for m in errors(issues))


def test_university_style_course_codes_are_accepted():
    data = {"credit_summary": {}, "semester_structure": [_course(course_code="26BCC1C01")]}
    issues, _ = validate_stage("prog_curriculum", data, ctx("UG - 3 Year", 6))
    assert not any("Course code" in m and "expected format" in m for m in errors(issues))


def test_a_course_may_repeat_across_the_two_honours_tracks():
    rows = [_course(course_code="26BCC7C01", semester=7, track="Honours"),
            _course(course_code="26BCC7C01", semester=7, track="Honours with Research")]
    issues, _ = validate_stage("prog_curriculum", {"credit_summary": {}, "semester_structure": rows},
                               ctx("UG - 4 Year (Honours)", 8))
    assert not any("used twice" in m for m in errors(issues))


def test_ugc_table2_is_worked_out_from_the_programme_structure():
    """Nothing is typed into a credit grid: the categories are added up from
    the courses, and only this programme's semester 7-8 track counts."""
    rows = [_course(credits=4, l=4, total_marks=100, cia=50, ese=50),
            _course(course_code="R7", semester=7, credits=4, l=4, total_marks=100, cia=50,
                    ese=50, nep_category="Research Project / Dissertation",
                    track="Honours with Research")]
    issues, _ = validate_stage("prog_curriculum", {"semester_structure": rows},
                               ctx("UG - 4 Year (Honours)", 8))
    msgs = errors(issues)
    assert any("Major (Core): 4 credits is below the UGC minimum" in m for m in msgs)
    assert any("Total credits come to 4." in m for m in msgs)

