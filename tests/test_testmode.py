"""Test mode: everything it offers, and that none of it exists when it is off."""

TEST_ROUTES = ["/test/", "/test/status"]
TEST_POSTS = ["/test/seed", "/test/signin", "/test/reset", "/test/open-all/COM"]


# --------------------------------------------------------------------------
# off by default
# --------------------------------------------------------------------------

def test_the_sandbox_does_not_exist_when_test_mode_is_off(client):
    for url in TEST_ROUTES:
        assert client.get(url).status_code == 404, url
    for url in TEST_POSTS:
        assert client.post(url).status_code == 404, url


def test_no_ribbon_and_no_quick_sign_in_when_it_is_off(client):
    assert "Test mode" not in client.get("/login").get_data(as_text=True)


def test_test_mode_is_off_unless_it_is_asked_for(app):
    assert app.config["TEST_MODE"] is False


# --------------------------------------------------------------------------
# on
# --------------------------------------------------------------------------

def test_the_console_opens_and_says_what_it_is(test_mode_client):
    body = test_mode_client.get("/test/").get_data(as_text=True)
    assert "Test console" in body
    assert "Sandbox data" in body


def test_every_page_carries_the_ribbon(test_mode_client):
    for url in ("/?home=1", "/login", "/test/"):
        assert "test-ribbon" in test_mode_client.get(url).get_data(as_text=True), url


def test_seeding_creates_the_demo_institution(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    with test_mode_app.app_context():
        db = get_db()
        assert db.departments.count_documents({}) == 7
        assert db.departments.count_documents({"campus": "Kochi"}) == 2
        assert db.users.count_documents({"role": "department"}) == 7


def test_seeding_twice_changes_nothing(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    r = test_mode_client.post("/test/seed", follow_redirects=True)
    assert "already in place" in r.get_data(as_text=True)
    with test_mode_app.app_context():
        assert get_db().departments.count_documents({}) == 7


def test_signing_in_without_a_password(test_mode_client, test_mode_app):
    test_mode_client.post("/test/seed", follow_redirects=True)
    r = test_mode_client.post("/test/signin", data={"username": "com"},
                              follow_redirects=True)
    assert r.status_code == 200
    assert test_mode_client.get("/department/").status_code == 200


def test_signing_in_as_the_administrator(test_mode_app, test_mode_client):
    r = test_mode_client.post("/test/signin",
                              data={"username": test_mode_app.config["ADMIN_USERNAME"]},
                              follow_redirects=True)
    assert r.status_code == 200
    assert test_mode_client.get("/admin/").status_code == 200


def test_an_unknown_account_is_refused(test_mode_client):
    r = test_mode_client.post("/test/signin", data={"username": "nobody"},
                              follow_redirects=True)
    assert "no account called" in r.get_data(as_text=True)


def test_a_disabled_account_is_refused(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    with test_mode_app.app_context():
        get_db().users.update_one({"username": "com"}, {"$set": {"active": False}})
    r = test_mode_client.post("/test/signin", data={"username": "com"},
                              follow_redirects=True)
    assert "disabled" in r.get_data(as_text=True)


def test_opening_every_stage_skips_the_sequential_lock(test_mode_client, test_mode_app):
    from app.db import get_db
    from app.schema import STAGE_KEYS
    from app.workflow import compute_status
    test_mode_client.post("/test/seed", follow_redirects=True)
    test_mode_client.post("/test/open-all/COM", follow_redirects=True)
    with test_mode_app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        assert all(compute_status(sub, k) == "open" for k in STAGE_KEYS)

    test_mode_client.post("/test/signin", data={"username": "com"}, follow_redirects=True)
    # The last stage, reachable without the twelve before it.
    assert test_mode_client.get(f"/department/stage/{STAGE_KEYS[-1]}").status_code == 200


def test_open_all_on_an_unknown_department_is_a_404(test_mode_client):
    assert test_mode_client.post("/test/open-all/NOSUCH").status_code == 404


def test_reset_needs_the_word_typed(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    r = test_mode_client.post("/test/reset", data={"confirm": "yes"}, follow_redirects=True)
    assert "Nothing has been deleted" in r.get_data(as_text=True)
    with test_mode_app.app_context():
        assert get_db().departments.count_documents({}) == 7


def test_reset_clears_the_sandbox_but_keeps_the_way_back_in(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    test_mode_client.post("/test/reset", data={"confirm": "RESET"}, follow_redirects=True)
    with test_mode_app.app_context():
        db = get_db()
        assert db.departments.count_documents({}) == 0
        assert db.users.count_documents({"role": "department"}) == 0
        assert db.users.count_documents({"role": "admin"}) == 1
        assert db.rules.find_one({"_id": "ugc"})
        assert db.settings.find_one({"_id": "app"})


def test_reset_can_seed_again_in_the_same_breath(test_mode_client, test_mode_app):
    from app.db import get_db
    test_mode_client.post("/test/seed", follow_redirects=True)
    test_mode_client.post("/test/reset", data={"confirm": "RESET", "reseed": "on"},
                          follow_redirects=True)
    with test_mode_app.app_context():
        assert get_db().departments.count_documents({}) == 7


def test_the_sign_in_screen_offers_the_demo_accounts(test_mode_client):
    test_mode_client.post("/test/seed", follow_redirects=True)
    body = test_mode_client.get("/login").get_data(as_text=True)
    assert "Sign in as anyone, no password" in body
    assert "com.bba" in body or "bba" in body


def test_the_status_endpoint_reports_the_sandbox(test_mode_client):
    test_mode_client.post("/test/seed", follow_redirects=True)
    data = test_mode_client.get("/test/status").get_json()
    assert data["test_mode"] is True
    assert data["departments"] == 7


def test_the_dev_server_seeds_the_same_institution(test_mode_app):
    from app.db import get_db
    from app.testmode import DEMO_DEPARTMENTS, seed_for_devserver
    with test_mode_app.app_context():
        rows = seed_for_devserver(get_db())
        assert len(rows) == len(DEMO_DEPARTMENTS)
        assert get_db().departments.count_documents({}) == len(DEMO_DEPARTMENTS)
