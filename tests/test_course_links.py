"""Each course row carries Syllabus and Revision (Yes / No, and a link);
a course marked No for revision is left out of Course Revision's fill-in,
and an earlier batch's course table has the same two columns."""

from app.schema import STAGE_BY_KEY


def _cols(stage_key, section_key):
    sec = next(s for s in STAGE_BY_KEY[stage_key]["sections"] if s["key"] == section_key)
    return [c["name"] for c in sec["columns"]]


def test_the_programme_structure_and_earlier_batches_have_syllabus_and_revision():
    assert _cols("prog_curriculum", "semester_structure")[-2:] == ["syllabus", "revision"]
    assert _cols("prog_syllabus_b2024", "batch_courses")[-2:] == ["syllabus", "revision"]


def test_a_course_not_revised_is_left_out_of_course_revision(app):
    from app.workflow import revision_fill_source
    sub = {"programmes": {"BCA": {
        "prog_curriculum": {"data": {"semester_structure": [
            {"semester": 1, "course_code": "C1", "course_title": "One", "credits": 4},
            {"semester": 1, "course_code": "C2", "course_title": "Two", "credits": 4, "revision": "No"},
        ]}},
        "prog_syllabus": {"data": {"courses": [
            {"course_code": "C1", "course_title": "One"}, {"course_code": "C2", "course_title": "Two"}]}},
    }}}
    with app.app_context():
        codes = [r["course_code"] for r in revision_fill_source(sub, "BCA")]
    assert codes == ["C1"]


def test_course_revision_finds_the_earlier_batch_course_whatever_its_year(app):
    from app.workflow import revision_fill_source
    sub = {"programmes": {"BCA": {
        "prog_curriculum": {"data": {"semester_structure": [
            {"semester": 1, "course_code": "26BCA1C01", "course_title": "Programming", "credits": 4}]}},
        "prog_syllabus": {"data": {"courses": [
            {"course_code": "26BCA1C01", "course_title": "Programming",
             "modules": [{"title": "Basics", "revised": "Variables and loops", "hours": 9}]}]}},
        "prog_syllabus_b2025": {"data": {"courses": [
            {"course_code": "25BCA1C01", "course_title": "Programming",
             "modules": [{"title": "Basics", "revised": "Variables", "hours": 9}]}]}},
    }}}
    with app.app_context():
        from app.db import get_db
        get_db().settings.update_one({"_id": "app"}, {"$set": {"current_batch": "2026-2027",
                                                               "existing_batches": ["2025-2026"]}}, upsert=True)
        row = revision_fill_source(sub, "BCA")[0]
    assert row["prev_code"] == "25BCA1C01" and row["year_previous"] == "2025"
    assert "Variables" in row["modules"][0]["previous"]


def test_an_earlier_batch_has_its_courses_and_their_syllabi_and_no_upload():
    sections = STAGE_BY_KEY["prog_syllabus_b2025"]["sections"]
    assert [s["key"] for s in sections] == ["batch_courses", "courses"]
    assert sections[1]["display"] == "sheet" and sections[1]["min_rows"] == 0
    assert not any(f.get("type") == "file" for s in sections for f in s.get("fields", []))


def test_semester_one_and_two_courses_cannot_be_marked_no():
    from app.validation import validate_stage
    rows = [
        {"semester": 1, "course_code": "C1", "syllabus": "No"},
        {"semester": 2, "course_code": "C2", "revision": "No"},
        {"semester": 3, "course_code": "C3", "syllabus": "No", "revision": "No"},
        {"semester": 2, "course_code": "C4", "syllabus": "Yes", "revision": "Yes"},
    ]
    issues, _ = validate_stage("prog_curriculum", {"semester_structure": rows}, {})
    msgs = [i["message"] for i in issues if "semester 1 or 2" in i["message"]]
    assert len(msgs) == 2 and "C1" in msgs[0] and "C2" in msgs[1]
    assert [i["row"] for i in issues if "semester 1 or 2" in i["message"]] == [0, 1]
    # an earlier batch has no such rule: it has no Yes / No at all
    batch, _ = validate_stage("prog_syllabus_b2025", {"batch_courses": rows}, {})
    assert not [i for i in batch if "semester 1 or 2" in i["message"]]
