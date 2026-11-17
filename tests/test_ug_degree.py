"""A UG programme's Curriculum does not ask for its degree: unless the
programme has one, its structure says — courses in semesters 7–8 make it a
4-year (Honours with Research) degree, otherwise 3-year. A PG programme is
still asked."""

from test_workflow import DEPT_INFO_OK, login, make_department

ROWS6 = [{"semester": 1, "course_code": "A1"}, {"semester": 6, "course_code": "A6"}]
ROWS8 = ROWS6 + [{"semester": 7, "course_code": "A7"}]


def test_the_degree_is_worked_out_from_the_structure():
    from app.workflow import apply_defaults, curriculum_degree
    assert curriculum_degree({"semester_structure": ROWS6}, "UG") == "UG - 3 Year"
    assert curriculum_degree({"semester_structure": ROWS8}, "UG") == "UG - 4 Year (Honours with Research)"
    # one the programme has is kept; one worked out before follows the structure as it is now
    named = {"details": {"degree_level": "UG - 4 Year (Honours)"}, "semester_structure": ROWS6}
    assert curriculum_degree(named, "UG") == "UG - 4 Year (Honours)"
    auto = {"details": {"degree_level": "UG - 3 Year", "_degree_auto": True}, "semester_structure": ROWS8}
    assert curriculum_degree(auto, "UG") == "UG - 4 Year (Honours with Research)"
    # nothing to go on yet, and a PG programme as the catalogue has it
    assert curriculum_degree({}, "UG") == ""
    assert curriculum_degree({}, "PG") == "PG - 2 Year"
    # checking and submitting fill it in for UG — not for PG, which is asked
    data = apply_defaults("prog_curriculum", {"details": {}, "semester_structure": ROWS8}, {"level": "UG"})
    assert data["details"]["degree_level"] == "UG - 4 Year (Honours with Research)"
    assert not apply_defaults("prog_curriculum", {"details": {}}, {"level": "PG"})["details"].get("degree_level")


def test_a_ug_curriculum_is_not_asked_for_its_degree(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    data = {"details": {}, "semester_structure": ROWS6}
    assert client.post("/department/api/prog_curriculum/BCMREG/save", json=data).get_json()["ok"]
    j = client.post("/department/api/prog_curriculum/BCMREG/validate", json=data).get_json()
    assert not [i for i in j["issues"] if "Degree / Duration" in i["message"]], j["issues"]
    # a worked-out 3-year degree does not shut semesters 7–8: they stay open to add
    data["details"] = {"degree_level": "UG - 3 Year", "_degree_auto": True}
    assert client.post("/department/api/prog_curriculum/BCMREG/save", json=data).get_json()["ok"]
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    import json
    stage = json.loads(page.split('<script id="stage-def" type="application/json">')[1].split("</script>")[0])
    sem = next(c for s in stage["sections"] if s["key"] == "semester_structure" for c in s["columns"]
               if c["name"] == "semester")
    assert sem.get("max") != 6


def test_without_courses_there_is_no_degree_to_work_out_and_none_is_asked():
    from app.schema import STAGE_BY_KEY, for_level
    from app.validation import validate_stage
    from app.workflow import apply_defaults
    out = apply_defaults("prog_curriculum", {"details": {}}, {"level": "UG"})
    assert not out["details"].get("degree_level")
    issues, _ = validate_stage("prog_curriculum", out)
    assert not [i for i in issues if "Degree / Duration" in i["message"]]
    # a PG programme is still asked
    pg = for_level(STAGE_BY_KEY["prog_curriculum"], "PG - 2 Year")
    field = next(f for s in pg["sections"] if s["key"] == "details" for f in s["fields"] if f["name"] == "degree_level")
    assert field["required"]
