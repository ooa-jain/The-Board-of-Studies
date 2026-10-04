"""The demo department: made from the admin side, filled like a real one,
signed in to, and taken away again."""

from test_workflow import login


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_the_demo_department_is_filled_and_can_sign_in(app, client):
    from app import demo_dept
    from app.db import get_db
    with app.app_context():
        user, pw, results = demo_dept.create("2027-28", app.config["UPLOAD_ROOT"])
        assert results == {"dept_info": "submitted", "pre_bos": "submitted"}, results
        db = get_db()
        assert db.files.count_documents({"dept_code": "DEMO"}) == 5
        miss = db.files.find_one({"dept_code": "DEMO", "field": "vision_mission"})
        assert miss["keyword_match"]["status"] == "miss"
        ok = db.files.find_one({"dept_code": "DEMO", "field": "minutes"})
        assert ok["keyword_match"]["status"] == "match"
        assert db.notifications.count_documents({"dept_code": "DEMO"}) == 5

    login(client, user, pw)
    body = client.get("/department/").get_data(as_text=True)
    assert "Demonstration Studies" in body


def test_the_admin_makes_and_removes_the_demo(app, client):
    from app.db import get_db
    _admin(app, client)
    r = client.post("/admin/demo-department", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Demonstration Studies" in body
    with app.app_context():
        assert get_db().departments.find_one({"dept_code": "DEMO"})
    client.post("/admin/demo-department/remove")
    with app.app_context():
        assert not get_db().departments.find_one({"dept_code": "DEMO"})
        assert not get_db().users.find_one({"dept_code": "DEMO"})
