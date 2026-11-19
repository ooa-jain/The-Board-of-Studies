"""The first time a department's login is used, the terms of use come first:
tick the box (keep a backup of what is submitted) and enter; never again."""

from test_workflow import login, make_department


def test_terms_once_per_department(app, client):
    from app.db import get_db
    app.config["ASK_TERMS"] = True
    try:
        u, p = make_department(app)
        login(client, u, p)
        r = client.get("/department/stage/pre_bos")
        assert r.status_code == 302 and "/department/terms" in r.headers["Location"]
        page = client.get("/department/terms?next=/department/stage/pre_bos").get_data(as_text=True)
        assert "Keep your own backup" in page and "Enter the portal" in page
        # not ticked: refused
        r = client.post("/department/terms", data={"next": "/department/stage/pre_bos"})
        assert b"Tick the box" in r.data
        r = client.post("/department/terms", data={"next": "/department/stage/pre_bos", "agree": "on"})
        assert r.status_code == 302 and r.headers["Location"].endswith("/department/stage/pre_bos")
        with app.app_context():
            t = get_db().departments.find_one({"dept_code": "COM"})["terms"]
            assert t["version"] and t["at"]
        assert client.get("/department/stage/pre_bos").status_code == 200
        # a fresh sign-in: not asked again
        client.get("/logout")
        login(client, u, p)
        assert client.get("/department/").status_code == 200
    finally:
        app.config["ASK_TERMS"] = False
