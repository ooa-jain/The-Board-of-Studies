"""Admin › Rules & UGC: each department, under its school, is UGC (3-year,
Honours, Honours with Research, checked against UGC Table 2) or No UGC
(semesters 1 to 8 in one flow, no UGC check)."""

import json

from test_workflow import login, make_department


def _admin(app, client):
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def _row(sem, cat, cr, i, track=None):
    r = {"semester": sem, "nep_category": cat, "course_code": f"26BC{i}", "course_title": f"Course {i}",
         "l": cr, "t": 0, "p": 0, "e": 0, "credits": cr, "cia": 50, "ese": 50, "total_marks": 100}
    if track:
        r["track"] = track
    return r


def _stage(page):
    return json.loads(page.split('id="stage-def" type="application/json">')[1].split("</script>")[0])


def test_departments_are_listed_under_their_school_and_saved(app, client):
    from app.db import get_db
    make_department(app, "COM", "Department of Commerce", "School of Commerce")
    make_department(app, "ENG", "Department of English", "School of Humanities")
    _admin(app, client)
    page = client.get("/admin/rules-ugc").get_data(as_text=True)
    assert "Rules &amp; UGC" in page and "School of Commerce" in page and "School of Humanities" in page
    assert 'name="mode.COM" value="ugc" checked' in page

    client.post("/admin/rules-ugc", data={"mode.COM": "flow", "mode.ENG": "ugc"})
    with app.app_context():
        assert get_db().departments.find_one({"dept_code": "COM"})["credit_rules"] == "flow"
        assert get_db().departments.find_one({"dept_code": "ENG"}).get("credit_rules") in (None, "ugc")
        assert get_db().audit.find_one({"action": "rules_ugc.flow"})
    page = client.get("/admin/rules-ugc").get_data(as_text=True)
    assert 'name="mode.COM" value="flow" checked' in page
    # an unknown value changes nothing
    client.post("/admin/rules-ugc", data={"mode.COM": "nonsense"})
    with app.app_context():
        assert get_db().departments.find_one({"dept_code": "COM"})["credit_rules"] == "flow"


def test_a_department_cannot_open_rules_and_ugc(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.get("/admin/rules-ugc").status_code in (302, 403)
    assert client.post("/admin/rules-ugc", data={"mode.COM": "flow"}).status_code in (302, 403)


def _set_flow(app):
    from app.db import get_db
    with app.app_context():
        get_db().departments.update_one({"dept_code": "COM"}, {"$set": {"credit_rules": "flow"}})


def test_no_ugc_curriculum_is_one_flow_without_ugc_checks(app, client):
    u, p = make_department(app)
    _set_flow(app)
    login(client, u, p)
    rows = [_row(1, "Major (Core)", 4, 0), _row(3, "Minor Stream", 3, 1),
            _row(7, "Major (Core)", 4, 2, "Honours"), _row(7, "Major (Core)", 4, 2, "Honours with Research"),
            _row(8, "Research Project / Dissertation", 6, 3, "Honours with Research")]
    client.post("/department/api/prog_curriculum/BCMREG/save", json={"semester_structure": rows})
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    stage = _stage(page)
    assert stage.get("flow") is True
    struct = next(s for s in stage["sections"] if s["key"] == "semester_structure")
    assert next(c for c in struct["columns"] if c["name"] == "semester")["choices"] == list(range(1, 9))
    summary = next(s for s in stage["sections"] if s["key"] == "credit_distribution")
    assert not any(r.startswith("ugc_") for r in summary.get("rules", []))
    data = json.loads(page.split('id="stage-data" type="application/json">')[1].split("</script>")[0])
    got = data["semester_structure"]
    # no Honours rows; the course listed under both is kept once
    assert all("track" not in r for r in got) and len(got) == 4
    assert "credits required" not in page          # no UGC Table 2 strip

    body = client.post("/department/api/prog_curriculum/BCMREG/validate",
                       json={"semester_structure": got}).get_json()
    msgs = " ".join(i["message"] for i in body.get("issues", []))
    assert "UGC" not in msgs and "outside this programme" not in msgs


def test_ugc_department_keeps_the_honours_split_and_checks(app, client):
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    assert not _stage(page).get("flow")
    body = client.post("/department/api/prog_curriculum/BCMREG/validate", json={
        "details": {"degree_level": "UG - 3 Year"},
        "semester_structure": [_row(1, "Major (Core)", 4, 0)]}).get_json()
    msgs = " ".join(i["message"] for i in body.get("issues", []))
    assert "UGC" in msgs
