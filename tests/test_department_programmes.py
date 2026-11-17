"""Departments › Edit: the department's own programme list, kept from year to
year (add, remove, put back), and its Rules (UGC / No UGC)."""

from test_workflow import PROGRAMMES_OK, login, make_department


def _admin(app, client):
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def _workbook(monkeypatch):
    """Two workbook programmes for the Department of Commerce."""
    from app import catalogue
    rows = ({"programme_code": "BCMREG", "programme_name": "Bachelor of Commerce", "degree": "UG",
             "year_introduced": "2009", "category": "", "minors": "", "department": "Department of Commerce",
             "location": "Global Campus", "kochi": False},
            {"programme_code": "MCMREG", "programme_name": "Master of Commerce", "degree": "PG",
             "year_introduced": "2010", "category": "", "minors": "", "department": "Department of Commerce",
             "location": "Global Campus", "kochi": False})
    monkeypatch.setattr(catalogue, "load", lambda: rows)


def test_edit_page_lists_adds_removes_and_puts_back(app, client, monkeypatch):
    from app.db import get_db
    from app.workflow import catalogue_rows
    _workbook(monkeypatch)
    make_department(app)
    _admin(app, client)
    page = client.get("/admin/departments/COM/edit").get_data(as_text=True)
    assert "BCMREG" in page and "MCMREG" in page and "Add a programme" in page
    assert 'name="credit_rules" value="ugc" checked' in page

    client.post("/admin/departments/COM/programme-list/MCMREG/remove")
    client.post("/admin/departments/COM/programme-list/add",
                data={"programme_code": "bcafin", "programme_name": "BCom in Fintech", "degree": "UG",
                      "year_introduced": "2026"})
    with app.app_context():
        dept = get_db().departments.find_one({"dept_code": "COM"})
        codes = [r["programme_code"] for r in dept["programmes_master"]]
        assert codes == ["BCMREG", "BCAFIN"]
        # every year that has not saved its list follows it
        assert [r["programme_code"] for r in catalogue_rows(dept)] == ["BCMREG", "BCAFIN"]
    page = client.get("/admin/departments/COM/edit").get_data(as_text=True)
    assert "Removed" in page and "Put back" in page

    client.post("/admin/departments/COM/programme-list/MCMREG/restore")
    with app.app_context():
        dept = get_db().departments.find_one({"dept_code": "COM"})
        assert {r["programme_code"] for r in dept["programmes_master"]} == {"BCMREG", "BCAFIN", "MCMREG"}

    # a duplicate is refused
    client.post("/admin/departments/COM/programme-list/add",
                data={"programme_code": "BCMREG", "programme_name": "Again", "degree": "UG"})
    with app.app_context():
        assert len(get_db().departments.find_one({"dept_code": "COM"})["programmes_master"]) == 3


def test_a_saved_year_list_follows_the_change(app, client, monkeypatch):
    from app.db import get_db
    _workbook(monkeypatch)
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save", json={"programmes_offered": PROGRAMMES_OK})
    _admin(app, client)
    client.post("/admin/departments/COM/programme-list/BCMREG/remove")
    client.post("/admin/departments/COM/programme-list/add",
                data={"programme_code": "BCMFIN", "programme_name": "BCom Fintech", "degree": "UG"})
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        rows = {r["programme_code"]: r for r in sub["stages"]["dept_info"]["data"]["programmes_offered"]}
    assert rows["BCMREG"]["decision"] == "remove"            # taken off; its record is kept
    assert rows["BCMFIN"]["decision"] == "keep" and rows["BCMFIN"]["source"] == "office"


def test_rules_are_saved_from_the_edit_page(app, client):
    from app.db import get_db
    make_department(app)
    _admin(app, client)
    client.post("/admin/departments/COM/edit", data={
        "dept_code": "COM", "dept_name": "Department of Commerce", "school": "School of Commerce",
        "campus": app.config["CAMPUSES"][0], "place": app.config["PLACES"][0], "active": "on",
        "credit_rules": "flow"})
    with app.app_context():
        assert get_db().departments.find_one({"dept_code": "COM"})["credit_rules"] == "flow"
    page = client.get("/admin/departments/COM/edit").get_data(as_text=True)
    assert 'name="credit_rules" value="flow" checked' in page
    # Disable is its own form, not a second submit of Save
    assert 'form="dept-toggle"' in page and 'id="dept-toggle"' in page


def test_a_department_cannot_change_the_list(app, client):
    u, p = make_department(app)
    login(client, u, p)
    r = client.post("/admin/departments/COM/programme-list/add",
                    data={"programme_code": "X1", "programme_name": "X", "degree": "UG"})
    assert r.status_code in (302, 403)
