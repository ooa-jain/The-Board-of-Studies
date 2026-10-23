"""A syllabus sheet follows the University's sample: Course Information taken
from the Curriculum table (never typed again), Course Objectives, the Course
Outcomes each with its Bloom's Taxonomy level, the CO-PO-PSO Mapping with its
Articulation row — as many POs and PSOs as the programme sets — the Course
Content, and the Text Books, Book References and Web References."""

import io

from test_workflow import login


def test_course_information_comes_from_the_curriculum_line():
    from app.schema import course_info
    r = {"semester": 1, "l": 2, "t": 0, "p": 2, "e": 3, "credits": 4, "cia": 70, "ese": 30}
    assert course_info(r) == {"semester": 1, "ltpe": "2-0-2-3", "hours_per_week": 7, "credits": 4,
                              "teaching_hours": 60, "ca_ese": "70:30"}
    # what the line does not have yet is left out, not guessed
    assert course_info({"credits": "3"}) == {"credits": 3, "teaching_hours": 45}
    assert course_info({}) == {}


def test_a_programme_sets_its_own_number_of_pos_and_psos():
    from app.schema import outcome_columns
    assert outcome_columns({}) == [f"PO{n}" for n in range(1, 10)] + [f"PSO{n}" for n in range(1, 5)]
    assert outcome_columns({"po_count": "6", "pso_count": "2"}) == \
        ["PO1", "PO2", "PO3", "PO4", "PO5", "PO6", "PSO1", "PSO2"]
    assert outcome_columns({"po_count": "12", "pso_count": "0"})[-1] == "PO12"
    assert len(outcome_columns({"po_count": "99", "pso_count": "x"})) == 13    # out of range: the defaults


def test_an_outcomes_opening_verb_suggests_its_level():
    from app.schema import bloom_level
    assert bloom_level("Apply fundamental accounting concepts") == 3
    assert bloom_level("Evaluate the choices.") == 5
    assert bloom_level("Design a ledger") == 6
    assert bloom_level("Be aware of things") is None
    assert bloom_level("") is None


def _sheet(**kw):
    c = {"course_code": "26BCM1C01", "course_title": "Financial Accounting",
         "co_table": [{"text": "Apply accounting concepts", "bloom": "3"},
                      {"text": "Prepare final accounts", "bloom": "3"}],
         "co_po": [{"PO1": "3", "PSO1": "2"}, {"PO2": "2"}]}
    c.update(kw)
    return {"courses": [c]}


def test_every_course_outcome_needs_its_level():
    from app.validation import r_outcomes_have_bloom_levels as rule
    assert rule(_sheet(), {}, "courses") == []
    issues = rule(_sheet(co_table=[{"text": "Apply concepts", "bloom": ""}]), {}, "courses")
    assert [i["level"] for i in issues] == ["error"] and "CO 1" in issues[0]["message"]
    # an older sheet, with its outcomes only as lines, is asked for the levels
    old = _sheet(outcomes="Apply\nPrepare")
    del old["courses"][0]["co_table"]
    assert rule(old, {}, "courses")[0]["level"] == "error"


def test_the_mapping_holds_three_two_one_or_dash():
    from app.validation import r_co_po_mapping_valid as rule
    assert rule(_sheet(), {}, "courses") == []
    issues = rule(_sheet(co_po=[{"PO1": "5"}, {"PO2": "2"}]), {}, "courses")
    assert any(i["level"] == "error" and "must be 3, 2, 1 or –" in i["message"] for i in issues)
    # a CO left unmapped is a warning; a course with no mapping at all is an error
    issues = rule(_sheet(co_po=[{"PO1": "3"}, {"PO1": "-"}]), {}, "courses")
    assert [i["level"] for i in issues] == ["warning"] and "CO2" in issues[0]["message"]
    issues = rule(_sheet(co_po=[]), {}, "courses")
    assert any(i["level"] == "error" and "fill in its CO-PO-PSO Mapping" in i["message"] for i in issues)


def test_the_page_and_the_word_syllabus_follow_the_sample(app, client):
    from docx import Document

    from app import demo_dept
    from app.db import get_db
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    items = client.get("/department/api/record?programme=DEMOBBA").get_json()["items"]

    # the Curriculum sets 6 POs and 2 PSOs: the syllabus maps to those
    cur = items[0]["data"]
    cur["details"].update(po_count="6", pso_count="2")
    assert client.post("/department/api/prog_curriculum/DEMOBBA/save", json=cur).get_json()["ok"]
    page = client.get("/department/stage/prog_syllabus/DEMOBBA").get_data(as_text=True)
    assert 'outcome_cols: ["PO1", "PO2", "PO3", "PO4", "PO5", "PO6", "PSO1", "PSO2"]' in page
    # each course's information is there already, from its line of the table
    first = next(r for r in cur["semester_structure"] if r.get("course_code") and "/" not in r["course_code"])
    assert f'"ltpe": "{first["l"]}-{first["t"]}-{first["p"]}-{first["e"]}"' in page.replace(".0", "")

    # the sample sheets pass the rules
    data = items[1]["data"]
    j = client.post("/department/api/prog_syllabus/DEMOBBA/validate", json=data).get_json()
    assert not [i for i in j["issues"] if i["level"] == "error"], j["issues"]

    from app.docgen import syllabus_docx
    with app.app_context():
        doc = Document(io.BytesIO(syllabus_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    text = "\n".join(p.text for p in doc.paragraphs)
    for heading in ("Course Information:", "Course Objectives:", "Course Outcomes (COs):",
                    "CO-PO-PSO Mapping:", "Course Content:", "Text Books:", "Book References:",
                    "3-High, 2-Medium, 1-Low"):
        assert heading in text, heading
    tables = [[[c.text for c in r.cells] for r in t.rows] for t in doc.tables]
    info = next(t for t in tables if t[0][0] == "Course Title")
    assert [row[0] for row in info] == ["Course Title", "Course Code", "Semester", "Credits"]
    assert [row[2] for row in info[1:]] == ["L-T-P-E", "Contact Hours", "CA: ESE"]
    outcomes = next(t for t in tables if t[0][0] == "Course Outcome")
    assert outcomes[0] == ["Course Outcome", "Description", "Bloom’s Taxonomy Level"]
    assert outcomes[1][0] == "CO 1" and outcomes[1][2] in {"1", "2", "3", "4", "5", "6"}
    mapping = next(t for t in tables if t[0][0] == "CO")
    assert mapping[0] == ["CO", "PO1", "PO2", "PO3", "PO4", "PO5", "PO6", "PSO1", "PSO2"]
    assert mapping[-1][0] == "Articulation" and len(mapping) == len(outcomes) + 1
