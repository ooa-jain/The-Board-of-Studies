"""Autosave and page loads ask the database as little as they need to: a save
fetches only the programme it is for, and leaves every other one as it was;
the settings are read once per request, and afresh once they are changed."""

from test_workflow import DEPT_INFO_OK, login, make_department


def _count_finds(monkeypatch, collection):
    """How many times `collection` is read, from here on."""
    import mongomock
    seen = {"n": 0}
    real = mongomock.collection.Collection.find_one

    def find_one(self, *a, **kw):
        if self.name == collection:
            seen["n"] += 1
        return real(self, *a, **kw)
    monkeypatch.setattr(mongomock.collection.Collection, "find_one", find_one)
    return seen


def test_a_save_touches_only_its_own_programme(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    a = {"details": {"degree_level": "UG - 3 Year"}, "semester_structure": [{"course_code": "A1"}]}
    b = {"details": {"degree_level": "PG - 2 Year"}, "semester_structure": [{"course_code": "B1"}]}
    assert client.post("/department/api/prog_curriculum/BCMREG/save", json=a).get_json()["ok"]
    assert client.post("/department/api/prog_curriculum/MCMNEW/save", json=b).get_json()["ok"]
    a["semester_structure"].append({"course_code": "A2"})
    assert client.post("/department/api/prog_curriculum/BCMREG/save", json=a).get_json()["ok"]
    with app.app_context():
        progs = get_db().submissions.find_one({})["programmes"]
        assert progs["MCMNEW"]["prog_curriculum"]["data"] == b
        assert progs["BCMREG"]["prog_curriculum"]["data"] == a
        # one person's saves within a few minutes are one version
        assert get_db().versions.count_documents({"stage": "prog_curriculum", "programme_code": "BCMREG"}) == 1
    # an unknown programme is still refused
    r = client.post("/department/api/prog_curriculum/NOPE/save", json=a)
    assert r.status_code == 404


def test_the_settings_are_read_once_a_request_and_afresh_when_changed(app, client, monkeypatch):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    seen = _count_finds(monkeypatch, "settings")
    assert client.get("/department/").status_code == 200
    assert seen["n"] == 1
    client.get("/logout")

    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    client.post("/admin/team/links", data={"share_links": "team"})
    with app.app_context():
        assert get_db().settings.find_one({"_id": "app"})["share_links"] == "team"
    assert b"open only for people signed in" in client.get("/admin/team").data


def test_a_caller_cannot_change_the_settings_for_the_next(app):
    from app.db import settings
    with app.test_request_context("/"):
        s = settings()
        s["academic_year"] = "1999-00"
        assert settings().get("academic_year") != "1999-00"
