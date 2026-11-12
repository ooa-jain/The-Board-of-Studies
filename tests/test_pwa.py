"""The portal installs as an app: a manifest with its name and icons, a
service worker at the site's root, and an Install app item for the Office."""

from test_workflow import login, make_department


def test_the_manifest_names_the_app_and_its_icons(app, client):
    assert client.get("/manifest.webmanifest").status_code == 404     # signed out: no app
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.mimetype == "application/manifest+json"
    m = r.get_json(force=True)
    assert m["name"] == "BoS Academic Portal" and m["display"] == "standalone" and m["scope"] == "/"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes and any(i.get("purpose") == "maskable" for i in m["icons"])
    for i in m["icons"]:
        assert client.get(i["src"]).status_code == 200


def test_the_service_worker_is_served_from_the_root_and_never_cached(client):
    r = client.get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.mimetype
    assert "no-cache" in r.headers.get("Cache-Control", "")
    assert b"offline.html" in r.data
    assert client.get("/static/offline.html").status_code == 200


def test_the_office_gets_install_app_and_shortcuts(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/storage").get_data(as_text=True)
    assert 'rel="manifest"' in page and 'id="app-install"' in page and 'id="app-dialog"' in page
    assert "setAppBadge" in page
    m = client.get("/manifest.webmanifest").get_json(force=True)
    assert [s["name"] for s in m["shortcuts"]] == ["Departments", "Updates", "Storage"]


def test_departments_are_not_offered_the_app(app, client):
    assert 'rel="manifest"' not in client.get("/").get_data(as_text=True)     # the sign-in page
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/").get_data(as_text=True)
    assert 'rel="manifest"' not in page and 'id="app-install"' not in page
    assert "unregister" in page              # an app installed before is taken off
    assert client.get("/manifest.webmanifest").status_code == 404
