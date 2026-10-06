"""A shared department login: who is working, who changed what, and going
back to an earlier version within five days. Also the admin calendar."""

from datetime import timedelta

from test_workflow import DEPT_INFO_OK, login, make_department


def _as(client, name, email):
    return client.post("/department/who", data={"name": name, "email": email, "next": "/department/"})


def test_a_department_is_asked_who_it_is(app, client):
    app.config["ASK_PERSON"] = True
    u, p = make_department(app)
    login(client, u, p)
    r = client.get("/department/")
    assert r.status_code == 302 and "/department/who" in r.headers["Location"]
    assert b"Who is working" in client.get("/department/who").data
    assert b"working e-mail" in _as(client, "Asha", "nope").data
    r = _as(client, "Asha Rao", "asha@jain.ac.in")
    assert r.status_code == 302 and r.headers["Location"].endswith("/department/")
    page = client.get("/department/").data
    assert b"Asha Rao" in page and b"Versions" in page


def test_a_second_person_is_told_who_else_is_on(app):
    app.config["ASK_PERSON"] = True
    u, p = make_department(app)
    one, two = app.test_client(), app.test_client()
    login(one, u, p)
    _as(one, "Asha Rao", "asha@jain.ac.in")
    one.get("/department/")
    login(two, u, p)
    page = two.get("/department/who").data
    assert b"Already signed in" in page and b"Asha Rao" in page


def test_versions_say_who_changed_what_and_can_be_restored(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    _as(client, "Asha Rao", "asha@jain.ac.in")
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "a@x.edu"}})
    # a second person, later
    _as(client, "Ravi Kumar", "ravi@jain.ac.in")
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "b@x.edu"}})

    with app.app_context():
        vs = list(get_db().versions.find().sort("at", 1))
        n = get_db().notifications.find_one({"person": "Ravi Kumar"})
    assert [v["name"] for v in vs] == ["Asha Rao", "Ravi Kumar"]
    assert n, "the Office's update says who"
    page = client.get("/department/versions").data.decode()
    assert "Asha Rao" in page and "Ravi Kumar" in page and "b@x.edu" in page and "Restore" in page

    r = client.post(f"/department/versions/{vs[0]['_id']}/restore")
    assert r.status_code == 302
    with app.app_context():
        sub = get_db().submissions.find_one({})
        assert sub["stages"]["dept_info"]["data"]["contact"]["office_email"] == "a@x.edu"
        assert get_db().versions.count_documents({"kind": "restore"}) == 1


def test_versions_older_than_five_days_go_and_submitted_cannot_be_restored(app, client):
    from app.db import get_db, now
    u, p = make_department(app)
    login(client, u, p)
    _as(client, "Asha Rao", "asha@jain.ac.in")
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "a@x.edu"}})
    with app.app_context():
        get_db().versions.update_many({}, {"$set": {"at": now() - timedelta(days=6)}})
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    with app.app_context():
        vs = list(get_db().versions.find())
    assert [v["kind"] for v in vs] == ["submit"], "the six-day-old version was dropped"
    client.post(f"/department/versions/{vs[0]['_id']}/restore")
    assert b"cannot be changed" in client.get("/department/versions").data


def test_admin_calendar_shows_days_with_activity(app, client):
    from app.db import now
    u, p = make_department(app)
    login(client, u, p)
    _as(client, "Asha Rao", "asha@jain.ac.in")
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "a@x.edu"}})
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    day = now().strftime("%Y-%m-%d")
    page = client.get(f"/admin/calendar?month={day[:7]}&day={day}").data.decode()
    assert "cd-saved" in page and "Asha Rao" in page
    assert client.get("/admin/calendar?month=garbage").status_code == 200
