"""The landing page is an introduction, and an introduction happens once."""

from app.public import SEEN_COOKIE


def test_first_visit_shows_the_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Bengaluru" in body and "Kochi" in body
    assert SEEN_COOKIE in r.headers.get("Set-Cookie", "")


def test_a_second_visit_goes_straight_to_sign_in(client):
    client.get("/")
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_the_introduction_can_always_be_reopened(client):
    client.get("/")
    r = client.get("/?home=1")
    assert r.status_code == 200
    assert "Two campuses, one submission process" in r.get_data(as_text=True)


def test_a_signed_in_admin_lands_on_the_dashboard(app, client):
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].rstrip("/").endswith("/admin")


def test_a_signed_in_department_lands_on_its_own_dashboard(app, client):
    from tests.test_workflow import make_department
    u, p = make_department(app, "LND", "Department of Landings")
    client.post("/login", data={"username": u, "password": p})
    r = client.get("/")
    assert r.status_code == 302
    assert "/department" in r.headers["Location"]


def test_the_masthead_points_a_signed_in_user_at_their_own_work(app, client):
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    body = client.get("/admin/").get_data(as_text=True)
    assert 'class="brand" href="/admin/"' in body


def test_a_fresh_browser_still_sees_it(client, app):
    client.get("/")
    assert client.get("/").status_code == 302
    other = app.test_client()
    assert other.get("/").status_code == 200
