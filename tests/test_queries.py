"""Department Information's faculty and student numbers, and the Query button:
Technical shows the Help sections, Academics raises a ticket for the Office."""

from test_workflow import DEPT_INFO_OK, login, make_department


def _admin(app, client):
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_faculty_and_student_numbers_are_needed_to_submit(app, client):
    u, p = make_department(app)
    login(client, u, p)
    bad = {k: v for k, v in DEPT_INFO_OK.items() if k != "strength"}
    body = client.post("/department/api/dept_info/submit", json=bad).get_json()
    assert body["ok"] is False
    msgs = " ".join(i["message"] for i in body["issues"])
    assert "Number of faculty" in msgs and "Students in 1st year" in msgs
    assert "Students in the final semester" in msgs

    neg = dict(DEPT_INFO_OK, strength={"faculty_count": -1, "students_first_year": 10,
                                       "students_final_semester": 9})
    body = client.post("/department/api/dept_info/submit", json=neg).get_json()
    assert body["ok"] is False

    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]


def test_department_page_shows_query_button(app, client):
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/stage/dept_info").get_data(as_text=True)
    assert 'id="query-btn"' in page and "Faculty and students" in page


def test_technical_query_lists_help_sections(app, client):
    u, p = make_department(app)
    login(client, u, p)
    d = client.get("/department/query/sections").get_json()
    assert d["help_url"].endswith("/department/help")
    if d["sections"]:
        assert d["sections"][0]["url"].endswith("/department/help#1")
        assert d["sections"][0]["title"]


def test_academic_query_becomes_a_ticket_the_office_resolves(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    r = client.post("/department/query", json={"subject": "Minor credits", "text": "x"})
    assert r.status_code == 400

    r = client.post("/department/query", json={"subject": "Minor credits",
                                                "text": "How many credits for the minor?",
                                                "page": "/department/stage/curriculum"}).get_json()
    assert r["ok"] and r["ticket"] == "Q-0001"
    r2 = client.post("/department/query", json={"text": "A second question"}).get_json()
    assert r2["ticket"] == "Q-0002"

    with app.app_context():
        t = get_db().queries.find_one({"ticket": "Q-0001"})
        assert t["dept_code"] == "COM" and t["status"] == "open"
        assert get_db().notifications.find_one({"event": "query"})

    # a department cannot see the Office's list
    assert client.get("/admin/queries").status_code in (302, 403)

    _admin(app, client)
    page = client.get("/admin/queries").get_data(as_text=True)
    assert "Q-0001" in page and "How many credits for the minor?" in page
    client.post(f"/admin/queries/{t['_id']}/status", data={"status": "resolved"})
    with app.app_context():
        assert get_db().queries.find_one({"ticket": "Q-0001"})["status"] == "resolved"
    page = client.get("/admin/queries?show=open").get_data(as_text=True)
    assert "Q-0001" not in page and "Q-0002" in page
    client.post(f"/admin/queries/{t['_id']}/status", data={"status": "open"})
    with app.app_context():
        assert get_db().queries.find_one({"ticket": "Q-0001"})["status"] == "open"
