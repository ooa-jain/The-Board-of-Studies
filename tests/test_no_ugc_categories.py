"""No UGC: Design, Allied Healthcare, Engineering and Law automatically; a
No UGC curriculum has no Minor, its own course categories (CC, PCC, BSC, ESC,
HSMC, DSE, PEC, OE, OEC, GEC, AEC, SEC, VAC, Internship, Project, Dissertation),
and no credit rule."""

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
    assert cat["option_labels"]["Major (Core)"] == "CC — Core Course"
    assert cat["option_labels"]["Multidisciplinary"] == "OE — Open Elective"
    for c in ("Programme Core Course (PCC)", "Basic Science Course (BSC)", "Engineering Science Course (ESC)",
              "Humanities, Social Sciences and Management Course (HSMC)", "Programme Elective Course (PEC)",
              "Open Elective Course (OEC)", "Generic Elective Course (GEC)", "Project (PROJ)"):
        assert c in cat["options"]
    # the language course is the same as a UGC department's
    assert cat["option_labels"]["Ability Enhancement Courses (AEC) - Language"] == \
        "Ability Enhancement / AEC (Language)"
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


def test_no_ugc_keeps_its_own_categories_and_the_word_file_counts_them(app, client):
    from app.docgen import _used_groups
    u, p = make_department(app, "COM", "Department of Commerce", "School of Design, Media and Creative Arts")
    login(client, u, p)
    rows = [_row(1, "Basic Science Course (BSC)", "B1", 4, 4),
            _row(1, "Engineering Science Course (ESC)", "E1", 3, 3),
            _row(5, "Programme Elective Course (PEC)", "P1", 3, 3),
            _row(8, "Project (PROJ)", "J1", 6, 6)]
    client.post("/department/api/prog_curriculum/BCMREG/save", json={"semester_structure": rows})
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    data = json.loads(page.split('id="stage-data" type="application/json">')[1].split("</script>")[0])
    # saved as entered, not folded into Major or Research
    assert [r["nep_category"] for r in data["semester_structure"]] == [
        "Basic Science Course (BSC)", "Engineering Science Course (ESC)",
        "Programme Elective Course (PEC)", "Project (PROJ)"]
    # the Classification of Credits has a column for each category used, and no others
    assert [g[1] for g in _used_groups(data["semester_structure"], flow=True)] == \
        ["BSC", "ESC", "PEC", "Project / PROJ"]


def test_no_ugc_word_file_shows_the_new_categories(app, client):
    import io

    from docx import Document

    from app import demo_dept
    from app.db import get_db
    from app.docgen import curriculum_docx
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
        get_db().departments.update_one({"dept_code": "DEMO"}, {"$set": {"credit_rules": "flow"}})
    login(client, user, pw)
    rows = [_row(1, "Basic Science Course (BSC)", "BS1", 4, 4), _row(3, "Programme Core Course (PCC)", "PC1", 3, 3),
            _row(8, "Project (PROJ)", "PR1", 6, 6)]
    client.post("/department/api/prog_curriculum/DEMOBBA/save", json={"semester_structure": rows})
    with app.app_context():
        doc = Document(io.BytesIO(curriculum_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert "BASIC SCIENCE COURSES (BSC)" in cells and "PROGRAMME CORE COURSES (PCC)" in cells
    assert "PCC" in cells and "Project / PROJ" in cells and "Category" in cells
