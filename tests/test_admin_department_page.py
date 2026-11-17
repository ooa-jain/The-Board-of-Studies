"""Admin → a department: its details, any academic year, its programmes added,
changed and taken off, and the Office editing the department's own pages."""

from test_workflow import PROGRAMMES_OK, login, make_department


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def _seed(app, year="2027-28", rows=PROGRAMMES_OK):
    from app.db import get_db
    with app.app_context():
        get_db().submissions.insert_one({
            "dept_code": "COM", "academic_year": year, "status": "in_progress",
            "stages": {"dept_info": {"status": "draft", "data": {"programmes_offered": [dict(r) for r in rows]}}},
            "programmes": {"BCMREG": {"prog_curriculum": {"data": {"details": {"specialisation": "General"}}}}}})


def _list(app, year="2027-28"):
    from app.db import get_db
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM", "academic_year": year})
        return sub["stages"]["dept_info"]["data"]["programmes_offered"], sub


def test_department_name_opens_its_page_with_details_and_programmes(app, client):
    make_department(app)
    _seed(app)
    _admin(app, client)
    body = client.get("/admin/departments").get_data(as_text=True)
    assert "/admin/overview/departments/COM" in body
    page = client.get("/admin/overview/departments/COM").get_data(as_text=True)
    assert "Department details" in page and "Department of Commerce" in page
    assert "Programmes · 2027–28" in page
    for code in ("BCMREG", "BCHCOF", "MCMNEW"):
        assert code in page
    assert "Not this year" in page                       # BCHCOF is not run
    assert "+ Add programme" in page and "Edit as the Office" in page


def test_year_picker_lists_every_year_and_shows_that_year(app, client):
    make_department(app)
    _seed(app)
    _seed(app, "2026-27", [{"programme_code": "OLDPRG", "programme_name": "An older programme", "degree": "UG",
                            "source": "catalogue", "decision": "keep"}])
    _admin(app, client)
    page = client.get("/admin/overview/departments/COM").get_data(as_text=True)
    assert 'value="2026-27"' in page and 'value="2027-28"' in page
    old = client.get("/admin/overview/departments/COM?year=2026-27").get_data(as_text=True)
    assert "Programmes · 2026–27" in old and "OLDPRG" in old and "MCMNEW" not in old


def test_admin_adds_changes_and_removes_a_programme(app, client):
    make_department(app)
    _seed(app)
    _admin(app, client)
    r = client.post("/admin/departments/COM/programmes",
                    data={"year": "2027-28", "programme_code": "bcmfin", "programme_name": "B.Com Finance",
                          "degree": "UG", "category": "Commerce", "year_introduced": "2024"})
    assert r.status_code == 302
    rows, _ = _list(app)
    new = next(x for x in rows if x["programme_code"] == "BCMFIN")
    assert new["decision"] == "keep" and new["source"] == "office" and new["year_introduced"] == "2024"

    # change: name and code — its record follows the code
    client.post("/admin/departments/COM/programmes",
                data={"year": "2027-28", "was": "BCMREG", "programme_code": "BCMGEN",
                      "programme_name": "Bachelor of Commerce (General)", "degree": "UG"})
    rows, sub = _list(app)
    assert any(x["programme_code"] == "BCMGEN" and x["programme_name"] == "Bachelor of Commerce (General)" for x in rows)
    assert not any(x["programme_code"] == "BCMREG" for x in rows)
    assert "BCMGEN" in sub["programmes"] and "BCMREG" not in sub["programmes"]

    # a code already in the list is refused
    client.post("/admin/departments/COM/programmes",
                data={"year": "2027-28", "programme_code": "MCMNEW", "programme_name": "Again", "degree": "PG"})
    rows, _ = _list(app)
    assert sum(x["programme_code"] == "MCMNEW" for x in rows) == 1

    # remove, then put back
    client.post("/admin/departments/COM/programmes/MCMNEW/run", data={"year": "2027-28", "run": "0"})
    rows, _ = _list(app)
    assert next(x for x in rows if x["programme_code"] == "MCMNEW")["decision"] == "remove"
    client.post("/admin/departments/COM/programmes/MCMNEW/run", data={"year": "2027-28", "run": "1"})
    rows, _ = _list(app)
    assert next(x for x in rows if x["programme_code"] == "MCMNEW")["decision"] == "keep"


def test_programme_change_in_an_earlier_year_stays_in_that_year(app, client):
    make_department(app)
    _seed(app)
    _seed(app, "2026-27", [])
    _admin(app, client)
    client.post("/admin/departments/COM/programmes",
                data={"year": "2026-27", "programme_code": "OLDONE", "programme_name": "Old one", "degree": "UG"})
    old, _ = _list(app, "2026-27")
    now, _ = _list(app, "2027-28")
    assert [x["programme_code"] for x in old] == ["OLDONE"]
    assert "OLDONE" not in [x["programme_code"] for x in now]


def test_department_still_adds_its_own_programmes(app, client):
    """Both: the department's own Department Information still saves its list."""
    user, pw = make_department(app)
    login(client, user, pw)
    r = client.post("/department/api/dept_info/save",
                    json={"programmes_offered": PROGRAMMES_OK + [{"programme_code": "DEPNEW", "programme_name": "Its own",
                                                                  "degree": "UG", "source": "new", "decision": "keep"}]})
    assert r.status_code == 200
    rows, _ = _list(app)
    assert any(x["programme_code"] == "DEPNEW" for x in rows)


def test_office_edits_a_submitted_stage_in_the_departments_pages(app, client):
    make_department(app)
    _seed(app)
    from app.db import get_db
    with app.app_context():
        get_db().submissions.update_one({"dept_code": "COM", "academic_year": "2027-28"},
                                        {"$set": {"stages.dept_info.status": "submitted"}})
    _admin(app, client)
    # a department's pages are not the Office's until it asks to edit
    assert client.get("/department/").status_code == 403
    r = client.post("/admin/departments/COM/edit-as", data={"year": "2027-28", "next": "/department/stage/dept_info"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/department/stage/dept_info")
    page = client.get("/department/stage/dept_info").get_data(as_text=True)
    assert "You are editing" in page and "Department of Commerce" in page and "Back to admin" in page
    assert "Change Password" not in page
    # a submitted stage can be changed by the Office, and stays submitted
    r = client.post("/department/api/dept_info/save", json={"programmes_offered": PROGRAMMES_OK})
    assert r.status_code == 200
    with app.app_context():
        st = get_db().submissions.find_one({"dept_code": "COM", "academic_year": "2027-28"})["stages"]["dept_info"]
        assert st["status"] == "submitted"
        v = get_db().versions.find_one({"dept_code": "COM", "stage": "dept_info"})
        assert v and "Office of Academic Affairs" in str(v)
    # back to the Office's own pages
    r = client.get("/admin/edit-as/stop")
    assert r.status_code == 302 and "/admin/overview/departments/COM" in r.headers["Location"]
    assert client.get("/department/").status_code == 403


def test_edit_as_goes_only_to_the_departments_pages(app, client):
    make_department(app)
    _admin(app, client)
    r = client.post("/admin/departments/COM/edit-as", data={"year": "2027-28", "next": "https://example.com/x"})
    assert r.headers["Location"].endswith("/department/")


def test_a_department_cannot_reach_the_admin_programme_routes(app, client):
    user, pw = make_department(app)
    login(client, user, pw)
    assert client.post("/admin/departments/COM/programmes", data={"programme_code": "X1", "programme_name": "X"}).status_code in (302, 403)
    assert client.post("/admin/departments/COM/edit-as", data={}).status_code in (302, 403)
