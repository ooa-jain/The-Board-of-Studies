"""No UGC: Design, Allied Healthcare, Engineering and Law automatically; a
No UGC curriculum has no Minor, keeps DSE on its own, calls Multidisciplinary
GEC / OE / MDC, and has no credit rule."""

import json

from test_workflow import login, make_department


def _row(sem, cat, code, l, cr):
    return {"semester": sem, "nep_category": cat, "course_code": code, "course_title": f"Course {code}",
            "l": l, "t": 0, "p": 0, "e": 0, "credits": cr, "cia": 50, "ese": 50, "total_marks": 100}


def test_design_healthcare_engineering_and_law_are_no_ugc_automatically():
    from app.schema import credit_mode
    assert credit_mode({"school": "School of Design, Media and Creative Arts"}) == "flow"
    assert credit_mode({"faculty": "Faculty of Creativity and Design"}) == "flow"
    assert credit_mode({"school": "School of Allied Healthcare and Sciences"}) == "flow"
    assert credit_mode({"faculty": "Faculty of Engineering and Technology",
                        "school": "School of Computer Science and Engineering"}) == "flow"
    assert credit_mode({"school": "School of Aerospace Engineering"}) == "flow"
    assert credit_mode({"school": "School of Law"}) == "flow"
    for school in ("School of Commerce", "CMS Business School", "School of Sciences",
                   "School of Humanities and Social Sciences", "School of Computer Science and IT"):
        assert credit_mode({"school": school}) == "ugc", school
    # the Office's own choice wins
    assert credit_mode({"school": "School of Law", "credit_rules": "ugc"}) == "ugc"
    assert credit_mode({"school": "School of Commerce", "credit_rules": "flow"}) == "flow"


def test_rules_page_marks_the_automatic_ones(app, client):
    from app.db import get_db
    make_department(app, "LAW", "Department of Law", "School of Law")
    make_department(app, "COM", "Department of Commerce", "School of Commerce")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/rules-ugc").get_data(as_text=True)
    assert 'name="mode.LAW" value="flow" checked' in page and "No UGC automatically" in page
    assert 'name="mode.COM" value="ugc" checked' in page
    # saving as shown changes nothing and stores nothing
    client.post("/admin/rules-ugc", data={"mode.LAW": "flow", "mode.COM": "ugc"})
    with app.app_context():
        assert "credit_rules" not in get_db().departments.find_one({"dept_code": "LAW"})
    # the Office can still put one back on UGC
    client.post("/admin/rules-ugc", data={"mode.LAW": "ugc", "mode.COM": "ugc"})
    with app.app_context():
        assert get_db().departments.find_one({"dept_code": "LAW"})["credit_rules"] == "ugc"


def test_no_ugc_curriculum_categories_and_no_credit_rule(app, client):
    u, p = make_department(app, "COM", "Department of Commerce", "School of Design, Media and Creative Arts")
    login(client, u, p)
    rows = [_row(1, "Major (Core)", "C1", 4, 4),
            _row(5, "Discipline Specific Elective (DSE)", "D1", 3, 3),
            # credits that do not follow L-T-P-E, and more than 8: no credit rule here
            _row(6, "Multidisciplinary", "G1", 2, 10)]
    client.post("/department/api/prog_curriculum/BCMREG/save", json={"semester_structure": rows})
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    stage = json.loads(page.split('id="stage-def" type="application/json">')[1].split("</script>")[0])
    assert stage.get("flow") is True
    assert not any(s["key"] == "minors" for s in stage["sections"])
    struct = next(s for s in stage["sections"] if s["key"] == "semester_structure")
    cat = next(c for c in struct["columns"] if c["name"] == "nep_category")
    assert "Minor Stream" not in cat["options"] and "Discipline Specific Elective (DSE)" in cat["options"]
    assert cat["option_labels"]["Major (Core)"] == "Major / CC / Core"
    assert cat["option_labels"]["Multidisciplinary"] == "GEC / OE / MDC"
    assert "ltpe_credit_arithmetic" not in struct.get("rules", [])
    data = json.loads(page.split('id="stage-data" type="application/json">')[1].split("</script>")[0])
    # DSE stays DSE (a UGC department reads it as Major)
    assert data["semester_structure"][1]["nep_category"] == "Discipline Specific Elective (DSE)"

    body = client.post("/department/api/prog_curriculum/BCMREG/validate",
                       json={"semester_structure": rows}).get_json()
    msgs = " ".join(i["message"] for i in body.get("issues", []) if i.get("section") == "semester_structure")
    assert "works out to" not in msgs and "ceiling" not in msgs and "listed choices" not in msgs


def test_ugc_department_still_folds_dse_and_checks_credits(app, client):
    u, p = make_department(app)
    login(client, u, p)
    rows = [_row(1, "Major (Core)", "C1", 2, 6)]
    body = client.post("/department/api/prog_curriculum/BCMREG/validate",
                       json={"semester_structure": rows}).get_json()
    msgs = " ".join(i["message"] for i in body.get("issues", []))
    assert "works out to" in msgs
