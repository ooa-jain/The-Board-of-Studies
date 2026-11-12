"""A PO or PSO taken out of the Curriculum, the first included: the ones after
it move up, and every course's CO-PO-PSO Mapping and Articulation move with
them, so each figure stays under the outcome it was given for."""

from app.workflow import outcome_moves, save_draft, submit_stage


def _profile(pos, psos=("p",)):
    return {"programme_outcomes": list(pos), "programme_specific_outcomes": list(psos)}


def test_moves_name_the_one_taken_out_and_those_after_it():
    assert outcome_moves(_profile("abc"), _profile("bc")) == {"PO1": None, "PO2": "PO1", "PO3": "PO2"}
    assert outcome_moves(_profile("abc"), _profile("ac")) == {"PO2": None, "PO3": "PO2"}
    # the last one, one added, or only text changed: nothing moves
    assert outcome_moves(_profile("abc"), _profile("ab")) == {}
    assert outcome_moves(_profile("abc"), _profile("abcd")) == {}
    assert outcome_moves(_profile("abc"), _profile("xbc")) == {}
    # PSOs too
    assert outcome_moves(_profile("a", "xyz"), _profile("a", "yz")) == {"PSO1": None, "PSO2": "PSO1", "PSO3": "PSO2"}


def _seed(dbx):
    course = {"course_code": "C1", "co_table": [{"text": "x"}],
              "co_po": [{"PO1": "1", "PO2": "2", "PO3": "3", "PSO1": "3"}],
              "articulation": {"PO1": "1", "PO2": "2", "PO3": "3", "PSO1": "3"}}
    dbx.submissions.insert_one({
        "dept_code": "D1", "academic_year": "2027-28", "stages": {},
        "programmes": {"P1": {
            "prog_curriculum": {"data": {"profile": _profile(["one", "two", "three"])}},
            "prog_syllabus": {"data": {"courses": [dict(course)]}},
            "prog_syllabus_b2025": {"data": {"courses": [dict(course)]}},
        }}})


def _course(dbx, key):
    sub = dbx.submissions.find_one({"dept_code": "D1"})
    return sub["programmes"]["P1"][key]["data"]["courses"][0]


def test_removing_po1_moves_every_courses_mapping(dbx):
    _seed(dbx)
    save_draft("D1", "2027-28", "prog_curriculum", {"profile": _profile(["two", "three"])}, "P1")
    for key in ("prog_syllabus", "prog_syllabus_b2025"):
        c = _course(dbx, key)
        assert c["co_po"] == [{"PO1": "2", "PO2": "3", "PSO1": "3"}]
        assert c["articulation"] == {"PO1": "2", "PO2": "3", "PSO1": "3"}


def test_typing_in_a_po_moves_nothing(dbx):
    _seed(dbx)
    save_draft("D1", "2027-28", "prog_curriculum", {"profile": _profile(["one!", "two", "three"])}, "P1")
    assert _course(dbx, "prog_syllabus")["co_po"] == [{"PO1": "1", "PO2": "2", "PO3": "3", "PSO1": "3"}]


def test_submitting_after_a_removal_moves_them_too(app, dbx):
    _seed(dbx)
    with app.test_request_context():
        submit_stage("D1", "2027-28", "prog_curriculum", {"profile": _profile(["one", "three"])},
                     {"programme_code": "P1"})
    assert _course(dbx, "prog_syllabus")["co_po"] == [{"PO1": "1", "PO2": "3", "PSO1": "3"}]


def test_every_po_has_a_remove_button(client):
    """The page's PO/PSO list offers × on each one, the first included."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "stage.js").read_text(encoding="utf-8")
    assert "items.splice(i, 1)" in js
    assert "i === items.length - 1) {" not in js
