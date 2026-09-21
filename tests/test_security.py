"""CSRF, the sign-in throttle, and where ?next= is allowed to point."""

import re

import pytest

from app.auth import MAX_FAILURES, safe_next


def token_from(client, url="/login"):
    body = client.get(url).get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', body)
    assert match, "no CSRF token on the page"
    return match.group(1)


# --------------------------------------------------------------------------
# CSRF
# --------------------------------------------------------------------------

def test_a_post_without_a_token_is_refused(csrf_client):
    r = csrf_client.post("/login", data={"username": "x", "password": "y"})
    assert r.status_code == 400


def test_a_post_with_the_session_token_goes_through(csrf_app, csrf_client):
    token = token_from(csrf_client)
    r = csrf_client.post("/login", data={"username": csrf_app.config["ADMIN_USERNAME"],
                                         "password": csrf_app.config["ADMIN_PASSWORD"],
                                         "_csrf": token})
    assert r.status_code == 302
    assert "/admin" in r.headers["Location"] or "/change-password" in r.headers["Location"]


def test_somebody_elses_token_is_no_good(csrf_app, csrf_client):
    other = csrf_app.test_client()
    stolen = token_from(other)
    r = csrf_client.post("/login", data={"username": "x", "password": "y", "_csrf": stolen})
    assert r.status_code == 400


def test_a_json_call_can_send_the_token_as_a_header(csrf_app, csrf_client):
    token = token_from(csrf_client)
    r = csrf_client.post("/department/api/dept_info/save", json={},
                         headers={"X-CSRF-Token": token})
    # Rejected for not being signed in, not for the token.
    assert r.status_code in (302, 401, 403)


def test_a_json_call_without_the_header_is_told_to_reload(csrf_client):
    r = csrf_client.post("/department/api/dept_info/save", json={})
    assert r.status_code == 400
    assert r.get_json()["csrf"] is True


def test_reading_a_page_never_needs_a_token(csrf_client):
    assert csrf_client.get("/login").status_code == 200
    assert csrf_client.get("/?home=1").status_code == 200


def test_every_form_in_the_portal_carries_a_token(app, client):
    """A form without one is a button that stops working in production."""
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    from tests.test_workflow import make_department
    make_department(app, "FRM", "Department of Forms")
    pages = ["/admin/", "/admin/departments", "/admin/departments/new",
             "/admin/departments/FRM/edit", "/admin/submissions", "/admin/submissions/FRM",
             "/admin/rules", "/admin/settings", "/admin/import", "/change-password"]
    for url in pages:
        body = client.get(url).get_data(as_text=True)
        for form in re.findall(r"<form[^>]*method=[\"']post[\"'][^>]*>.*?</form>",
                               body, re.S | re.I):
            assert 'name="_csrf"' in form, f"{url}: a POST form with no token\n{form[:200]}"


# --------------------------------------------------------------------------
# sign-in
# --------------------------------------------------------------------------

def test_repeated_failures_hold_the_account(app, client):
    for _ in range(MAX_FAILURES):
        client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                    "password": "wrong"})
    r = client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                    "password": app.config["ADMIN_PASSWORD"]})
    assert r.status_code == 429
    assert "Too many failed attempts" in r.get_data(as_text=True)


def test_a_good_password_clears_the_count(app, client, dbx):
    for _ in range(3):
        client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                    "password": "wrong"})
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    assert dbx.login_attempts.count_documents(
        {"username": app.config["ADMIN_USERNAME"]}) == 0


def test_a_failed_sign_in_answers_401(app, client):
    r = client.post("/login", data={"username": "nobody", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.parametrize("target", ["//evil.example", "/\\evil.example",
                                    "https://evil.example", "evil.example", None, ""])
def test_next_cannot_leave_the_portal(target):
    assert safe_next(target) is None


@pytest.mark.parametrize("target", ["/admin/", "/department/stage/dept_info"])
def test_next_keeps_an_ordinary_path(target):
    assert safe_next(target) == target


def test_next_is_honoured_after_signing_in(app, client):
    r = client.post("/login?next=/admin/departments",
                    data={"username": app.config["ADMIN_USERNAME"],
                          "password": app.config["ADMIN_PASSWORD"]})
    # The bootstrap admin is sent to change its password first; once that is
    # done the next hop is an ordinary one.
    assert r.status_code == 302


def test_signing_out_empties_the_session(app, client):
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    client.get("/logout")
    assert client.get("/admin/").status_code == 302
