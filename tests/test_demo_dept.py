"""The demo department: every stage filled in and saved, so signing in as it
you only review and submit — and every stage does go through."""

from test_workflow import login


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_every_demo_stage_and_part_submits_as_filled(app, client):
    from app import demo_dept
    from app.db import get_db
    from app.schema import STAGE_BY_KEY, STAGE_KEYS
    with app.app_context():
        user, pw, results = demo_dept.create("2027-28", app.config["UPLOAD_ROOT"])
        db = get_db()
        assert db.files.count_documents({"dept_code": "DEMO"}) == 10
        bad = [r["original_name"] for r in db.files.find({"dept_code": "DEMO"})
               if r["keyword_match"]["status"] not in ("match", "unread")]
        assert not bad, f"demo files that fail the keyword check: {bad}"
        sub = db.submissions.find_one({"dept_code": "DEMO"})
        stored = {k: v["data"] for k, v in sub["stages"].items()}
        parts = {code: {k: v["data"] for k, v in p.items()} for code, p in sub["programmes"].items()}

    login(client, user, pw)
    assert "Demonstration Studies" in client.get("/department/").get_data(as_text=True)
    for key in STAGE_KEYS:
        if STAGE_BY_KEY[key].get("parts"):
            for code, by_part in parts.items():
                for part, data in by_part.items():
                    j = client.post(f"/department/api/{part}/{code}/submit", json=data).get_json()
                    errs = [i["message"] for i in j.get("issues", []) if i["level"] == "error"]
                    assert j["ok"], (code, part, errs[:5])
            continue
        j = client.post(f"/department/api/{key}/submit", json=stored[key]).get_json()
        errs = [i["message"] for i in j.get("issues", []) if i["level"] == "error"]
        assert j["ok"], (key, errs[:5])


def test_the_admin_makes_reviews_and_removes_the_demo(app, client):
    from app.db import get_db
    _admin(app, client)
    r = client.post("/admin/demo-department", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Demonstration Studies" in body and "data-review" in body
    j = client.get("/admin/submissions/DEMO/review/dept_info").get_json()
    assert j["stage"]["title"] == "Department Information" and j["data"]["programmes_offered"]
    j = client.get("/admin/submissions/DEMO/review/prog_curriculum?programme=DEMOBBA").get_json()
    assert len(j["data"]["semester_structure"]) == 38 and j["programme_name"].startswith("BBA")
    assert j["timing"]["started"]
    client.post("/admin/demo-department/remove")
    with app.app_context():
        assert not get_db().departments.find_one({"dept_code": "DEMO"})
        assert not get_db().users.find_one({"dept_code": "DEMO"})
