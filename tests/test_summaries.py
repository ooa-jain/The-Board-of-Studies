"""AI summaries of uploaded PDFs: text or pictures to Grok, kept once made,
and the admin sees the same summary. Grok itself is replaced by a stub."""

import io

from test_workflow import _tiny_pdf, login, make_department


def _text_pdf():
    import pypdfium2  # noqa: F401  (the renderer is what the portal reads with)
    try:
        import pymupdf
    except ImportError:
        import pytest
        pytest.skip("pymupdf not installed")
    d = pymupdf.open()
    page = d.new_page()
    y = 80
    for i in range(20):
        page.insert_text((72, y), f"Resolution {i + 1}: the board approved the curriculum.", fontsize=10)
        y += 16
    return d.tobytes()


def _upload(client, name, data, field="minutes"):
    return client.post("/department/api/upload", data={
        "file": (io.BytesIO(data), name), "stage": "bos_documents", "field": field,
    }, content_type="multipart/form-data").get_json()


def _stub(monkeypatch, calls):
    from app import summarise

    def fake(messages, model):
        content = messages[0]["content"]
        calls.append((model, "images" if isinstance(content, list) else "text", content))
        return "Minutes of the BoS meeting.\n- 9 members present.\nCheck: looks right."
    monkeypatch.setattr(summarise, "_call", fake)


def test_summary_is_off_without_a_key(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "m.pdf", _tiny_pdf())
    r = client.post(j["url"] + "/summary").get_json()
    assert not r["ok"] and "AI_API_KEY" in r["error"]


def test_a_text_pdf_is_summarised_once_and_kept(app, client, monkeypatch):
    app.config["AI_API_KEY"] = "test"
    calls = []
    _stub(monkeypatch, calls)
    u, p = make_department(app)
    login(client, u, p)

    j = _upload(client, "minutes.pdf", _text_pdf())
    r = client.post(j["url"] + "/summary").get_json()
    assert r["ok"] and "9 members" in r["summary"] and not r["cached"]
    assert calls[0][1] == "text"
    assert "Minutes of Meeting" in calls[0][2], "the box's label goes into the prompt"

    again = client.post(j["url"] + "/summary").get_json()
    assert again["cached"] and len(calls) == 1, "a kept summary is not asked for twice"

    client.post(j["url"] + "/summary?refresh=1")
    assert len(calls) == 2


def test_a_scan_is_sent_as_pictures(app, client, monkeypatch):
    app.config["AI_API_KEY"] = "test"
    calls = []
    _stub(monkeypatch, calls)
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "scan.pdf", _tiny_pdf())      # no text layer
    assert client.post(j["url"] + "/summary").get_json()["ok"]
    model, kind, content = calls[0]
    assert kind == "images"
    assert any(c.get("type") == "image_url" for c in content)


def test_only_pdfs_are_summarised(app, client, monkeypatch):
    app.config["AI_API_KEY"] = "test"
    _stub(monkeypatch, [])
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "list.docx", b"PK\x03\x04 not really a docx")
    r = client.post(j["url"] + "/summary").get_json()
    assert not r["ok"] and "PDF" in r["error"]


def test_the_admin_sees_documents_and_their_summaries(app, client, monkeypatch):
    app.config["AI_API_KEY"] = "test"
    calls = []
    _stub(monkeypatch, calls)
    u, p = make_department(app)
    with app.app_context():                 # open every stage, as in developer mode
        from app.db import get_db
        get_db().settings.update_one({"_id": "app"}, {"$set": {"dev_mode": True}}, upsert=True)
    login(client, u, p)
    j = _upload(client, "minutes.pdf", _text_pdf())
    saved = client.post("/department/api/bos_documents/save", json={"bos_files": {"minutes": {
        "name": j["name"], "stored": j["stored"], "size": j["size"], "url": j["url"]}}})
    client.post(j["url"] + "/summary")
    client.get("/logout")

    login(client, "ooa.admin", "TestAdminPassword1!")
    html = client.get("/admin/submissions/COM").get_data(as_text=True)
    assert "Uploaded documents" in html and "minutes.pdf" in html
    assert "9 members present" in html, "the kept summary shows without asking again"
    assert "Minutes of Meeting" in html

    r = client.get(f"/admin/documents/COM/{j['stored']}?inline=1")
    assert r.status_code == 200 and r.headers["Content-Type"] == "application/pdf"
    s = client.post(f"/admin/documents/COM/{j['stored']}/summary").get_json()
    assert s["ok"] and s["cached"] and len(calls) == 1


def test_a_department_cannot_reach_the_admin_document_routes(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "minutes.pdf", _tiny_pdf())
    r = client.get(f"/admin/documents/COM/{j['stored']}")
    assert r.status_code in (302, 403)


def test_a_refusal_says_xais_own_reason(app, monkeypatch):
    import urllib.error
    import urllib.request
    from app import summarise

    def refuse(*a, **kw):
        raise urllib.error.HTTPError(
            "u", 403, "Forbidden", {},
            io.BytesIO(b'{"code":"x","error":"Your team has no credits. Purchase them at console.x.ai"}'))
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with app.app_context():
        app.config["AI_API_KEY"] = "test"
        try:
            summarise._call([{"role": "user", "content": "hi"}], "grok-4")
        except summarise.SummaryError as e:
            msg = str(e)
    assert "403" in msg and "no credits" in msg


def test_a_busy_service_is_tried_again_then_explained(app, monkeypatch):
    import time
    import urllib.error
    import urllib.request
    from app import summarise
    tries = []

    def busy(*a, **kw):
        tries.append(1)
        raise urllib.error.HTTPError(
            "u", 429, "Too Many Requests", {},
            io.BytesIO(b'{"object":"error","message":"Requests rate limit exceeded","type":"rate_limited"}'))
    monkeypatch.setattr(urllib.request, "urlopen", busy)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    with app.app_context():
        app.config.update(AI_API_KEY="test", AI_NAME="Mistral")
        try:
            summarise._call([{"role": "user", "content": "hi"}], "mistral-small-latest")
        except summarise.SummaryError as e:
            msg = str(e)
    assert len(tries) == summarise.RETRIES
    assert "Mistral" in msg and "429" in msg and "rate limit exceeded" in msg
