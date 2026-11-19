"""Settings › Kochi login: a login for the Office of Academic Affairs, Kochi —
username and password made for it, Kochi departments only, and the Office
chooses View or Edit for each part of the menu."""

from test_workflow import login, make_department


def test_kochi_login_is_made_from_settings(app, client):
    from app.db import get_db
    make_department(app, "COM", "Department of Commerce", "School of Commerce")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/settings").get_data(as_text=True)
    assert "Kochi login" in page and "Create the Kochi login" in page

    form = client.get("/admin/team/new?for=kochi").get_data(as_text=True)
    assert 'value="Office of Academic Affairs, Kochi"' in form and 'value="ooa.kochi"' in form
    assert 'value="place:Kochi" checked' in form and "All Edit" in form

    data = {"name": "Office of Academic Affairs, Kochi", "email": "ooa.kochi", "preset": "custom",
            "pw_mode": "generate", "scope": "place:Kochi", "sec_home": "view", "sec_overview": "edit",
            "sec_settings": "view"}
    r = client.post("/admin/team/new", data=data)
    assert r.status_code == 302
    with app.app_context():
        u = get_db().users.find_one({"username": "ooa.kochi"})
        assert u and u["scope"]["places"] == ["Kochi"] and not u["scope"]["all"]
        assert u["access"]["sections"]["overview"] == "edit" and u["access"]["sections"]["home"] == "view"
        assert u["email"] == "" and u["must_change"]
    page = client.get("/admin/settings").get_data(as_text=True)
    assert "ooa.kochi" in page and "Change what it can view and edit" in page
    # a bad username is refused
    r = client.post("/admin/team/new", data={**data, "email": "a b", "name": "X"})
    assert b"username such as ooa.kochi" in r.data
