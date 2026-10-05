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
        user, pw = demo_dept.create("2027-28", app.config["UPLOAD_ROOT"])
        assert user == "demo.dept"
        db = get_db()
        assert not db.submissions.find_one({"dept_code": "DEMO"}), "the forms start empty"
        assert db.files.count_documents({"dept_code": "DEMO"}) == 10
        for r in db.files.find({"dept_code": "DEMO", "field": {"$in": ["diac_signed", "dpac_signed"]}}):
            assert r["keyword_match"]["template"]["ok"], r["keyword_match"]["template"]
        bad = [r["original_name"] for r in db.files.find({"dept_code": "DEMO"})
               if r["keyword_match"]["status"] not in ("match", "unread")]
        assert not bad, f"demo files that fail the keyword check: {bad}"

    login(client, user, pw)
    body = client.get("/department/").get_data(as_text=True)
    assert "Fill everything with sample data" in body
    client.post("/department/demo/fill-all")
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "DEMO"})
        stored = {k: v["data"] for k, v in sub["stages"].items()}
        parts = {code: {k: v["data"] for k, v in p.items()} for code, p in sub["programmes"].items()}
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
    assert "demo.dept" in body, "the login is shown on the Departments page"
    from app.db import get_db as _g
    with app.app_context():
        pw = _g().departments.find_one({"dept_code": "DEMO"})["initial_password"]
    assert pw in body
    # fill it as the department would, then review it from the admin side
    client.get("/logout")
    login(client, "demo.dept", pw)
    client.post("/department/demo/fill-all")
    client.get("/logout")
    _admin(app, client)
    assert "data-review" in client.get("/admin/submissions/DEMO").get_data(as_text=True)
    j = client.get("/admin/submissions/DEMO/review/dept_info").get_json()
    assert j["stage"]["title"] == "Department Information" and j["data"]["programmes_offered"]
    j = client.get("/admin/submissions/DEMO/review/prog_curriculum?programme=DEMOBBA").get_json()
    assert len(j["data"]["semester_structure"]) == 38 and j["programme_name"].startswith("BBA")
    assert j["timing"]["started"]
    client.post("/admin/demo-department/remove")
    with app.app_context():
        assert not get_db().departments.find_one({"dept_code": "DEMO"})
        assert not get_db().users.find_one({"dept_code": "DEMO"})


def test_only_the_step_that_completes_the_record_reviews_first(app, client):
    from app import demo_dept
    from app.db import get_db
    with app.app_context():
        user, pw = demo_dept.create("2027-28", app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    page = client.get("/department/stage/dept_info").get_data(as_text=True)
    assert "Submit this stage &amp; go to next" in page and "final: false" in page

    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "DEMO"})
    for key in ("dept_info", "pre_bos", "bos_documents"):
        assert client.post(f"/department/api/{key}/submit", json=sub["stages"][key]["data"]).get_json()["ok"]
    parts = [(code, part) for code in ("DEMOBBA", "DEMOBCOM")
             for part in ("prog_curriculum", "prog_syllabus", "prog_revision")]
    for code, part in parts[:-1]:
        data = sub["programmes"][code][part]["data"]
        assert client.post(f"/department/api/{part}/{code}/submit", json=data).get_json()["ok"]
    code, part = parts[-1]
    page = client.get(f"/department/stage/{part}/{code}").get_data(as_text=True)
    assert "final: true" in page, "the last step opens the review of everything"


def test_review_and_submit_all_stages_at_once(app, client):
    from app import demo_dept
    from app.db import get_db
    with app.app_context():
        user, pw = demo_dept.create("2027-28", app.config["UPLOAD_ROOT"])
    login(client, user, pw)

    # nothing filled: it stops at the first stage and says so
    j = client.post("/department/api/submit-all").get_json()
    assert not j["ok"] and j["failed"]["title"] == "Department Information"

    client.post("/department/demo/fill-all")
    rec = client.get("/department/api/record").get_json()
    titles = [i["title"] for i in rec["items"]]
    assert titles[:3] == ["Department Information", "Pre-BoS", "BoS Documents"]
    assert any("Course Revision" in t for t in titles)
    assert all(i["data"] for i in rec["items"]), "every stage is filled"

    j = client.post("/department/api/submit-all").get_json()
    assert j["ok"], j
    assert len(j["done"]) == len(rec["items"])
    with app.app_context():
        assert get_db().submissions.find_one({"dept_code": "DEMO"})["status"] == "sealed"
    page = client.get("/department/").get_data(as_text=True)
    assert "Review &amp; submit all stages" in page
