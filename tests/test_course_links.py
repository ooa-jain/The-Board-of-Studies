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
