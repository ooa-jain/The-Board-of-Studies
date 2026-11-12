"""Updates for the Office: what a department changed, field by field, the
bell's count, connectors that receive them, and the admin's keyword lists."""

import json

from test_summaries import _minutes_pdf, _upload
from test_workflow import DEPT_INFO_OK, login, make_department


def _admin(app, client):
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_a_save_is_recorded_field_by_field_and_folded(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "a@x.edu"}})
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "b@x.edu", "faculty_count": 12}})
    with app.app_context():
        notes = list(get_db().notifications.find({"event": "saved"}))
    assert len(notes) == 1, "two saves close together are one update"
    n = notes[0]
    assert n["saves"] == 2
    fields = {c["field"]: c for c in n["changes"]}
    assert any("mail" in f.lower() for f in fields), fields
    email = next(c for f, c in fields.items() if "mail" in f.lower())
    assert email["before"] == "—" and email["after"] == "b@x.edu"


def test_submit_and_upload_reach_the_admin(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    _upload(client, "minutes.pdf", _minutes_pdf(), field="minutes")
    _upload(client, "minutes.pdf", _minutes_pdf(), field="external_profiles")

    _admin(app, client)
    j = client.get("/admin/updates.json").get_json()
    assert j["unread"] >= 3
    body = client.get("/admin/updates").get_data(as_text=True)
    assert "Stage submitted" in body and "Department of Commerce" in body
    assert "Upload failed the keyword check" in body
    later = client.get("/admin/updates.json?after=2000-01-01T00:00:00").get_json()
    assert later["items"]

    client.post("/admin/updates/read")
    assert client.get("/admin/updates.json").get_json()["unread"] == 0


def test_a_connector_receives_the_update(app, client, monkeypatch):
    from app import notify
    sent = []
    monkeypatch.setattr(notify, "_post_json", lambda url, body: sent.append((url, body)) or 200)

    _admin(app, client)
    r = client.post("/admin/connectors", data={
        "kind": "slack", "name": "OOA Slack", "target": "https://hooks.slack.com/services/T/B/x",
        "events": ["submitted"]}, follow_redirects=True)
    assert "OOA Slack" in r.get_data(as_text=True)
    # a plain http address is refused
    r = client.post("/admin/connectors", data={"kind": "webhook", "target": "http://x", "events": ["saved"]},
                    follow_redirects=True)
    assert "must start with https://" in r.get_data(as_text=True)

    client.get("/logout")
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save", json={"contact": {"office_email": "a@x.edu"}})
    assert not sent, "saves are not sent unless chosen"
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    assert len(sent) == 1
    url, body = sent[0]
    assert url.startswith("https://hooks.slack.com") and "Stage submitted" in body["text"]


def test_the_admin_edits_keywords_and_rechecks(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "minutes.pdf", _minutes_pdf(), field="minutes")
    assert j["match"]["status"] == "match"

    _admin(app, client)
    body = client.get("/admin/keywords").get_data(as_text=True)
    assert "Minutes of Meeting" in body and "minutes.pdf" in body
    # words the minutes do not carry: checked again, they no longer match
    client.post("/admin/keywords", data={"kw_minutes": "zebra, giraffe, okapi"})
    client.post("/admin/keywords/recheck")
    with app.app_context():
        assert get_db().files.find_one({"field": "minutes"})["keyword_match"]["status"] == "miss"

    client.post("/admin/keywords/reset")
    client.post("/admin/keywords/recheck")
    with app.app_context():
        assert get_db().settings.find_one({"_id": "app"})["keywords"] == {}
        assert get_db().files.find_one({"field": "minutes"})["keyword_match"]["status"] == "match"


def test_every_settings_page_has_the_tabs(app, client):
    _admin(app, client)
    for url in ("/admin/settings", "/admin/keywords", "/admin/connectors", "/admin/rules", "/admin/audit"):
        body = client.get(url).get_data(as_text=True)
        assert 'class="admin-tabs"' in body, url
