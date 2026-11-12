"""Uploaded files in Google Drive: an upload is sent there and its id kept;
a server copy that is gone comes back from Drive when the file is opened;
deleting a department moves its files to the Drive bin. The Apps Script
itself is replaced by a stand-in that keeps files in a dict."""

import base64
import io

from test_workflow import _tiny_pdf, login, make_department


class _Now:
    """threading.Thread that runs at once, so the test sees the result."""
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


def _fake_drive(monkeypatch, app):
    from app import drive_store
    store, trashed = {}, []

    def call(payload, timeout=120, app=None):
        a = payload["action"]
        if a == "ping":
            return {"ok": True, "root": "ROOT"}
        if a == "put":
            fid = f"F{len(store) + 1}"
            store[fid] = (payload["path"], payload["name"], base64.b64decode(payload["data"]))
            return {"ok": True, "id": fid}
        if a == "get":
            return {"ok": True, "data": base64.b64encode(store[payload["id"]][2]).decode()}
        if a == "trash":
            trashed.append(payload["id"])
            return {"ok": True}
        raise AssertionError(a)

    monkeypatch.setattr(drive_store, "_call", call)
    monkeypatch.setattr(drive_store.threading, "Thread", _Now)
    app.config.update(FILE_STORE="drive", DRIVE_SCRIPT_URL="https://script.example/exec",
                      DRIVE_SCRIPT_SECRET="s3cret")
    return store, trashed


def test_an_upload_goes_to_drive_and_comes_back_when_the_server_copy_is_gone(app, client, monkeypatch):
    from app import drive_store
    from app.db import get_db
    store, trashed = _fake_drive(monkeypatch, app)
    u, p = make_department(app)
    login(client, u, p)
    pdf = _tiny_pdf()
    j = client.post("/department/api/upload", data={
        "file": (io.BytesIO(pdf), "minutes.pdf"), "stage": "bos_documents", "field": "minutes",
    }, content_type="multipart/form-data").get_json()
    assert j["ok"]
    with app.app_context():
        rec = get_db().files.find_one({"stored_name": j["stored"]})
        assert rec["drive_id"] == "F1" and "drive_error" not in rec
        folder, name, data = store["F1"]
        assert folder == f"{rec['academic_year']}/COM/bos_documents" and name == j["stored"] and data == pdf
        # the server copy is pruned; opening the file fetches it back from Drive
        path = drive_store.local_path(rec)
        path.unlink()
    r = client.get(j["url"])
    assert r.status_code == 200 and r.data == pdf
    with app.app_context():
        assert drive_store.local_path(rec).read_bytes() == pdf

    # deleting the department moves its files to the Drive bin
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    client.post("/admin/departments/COM/delete", data={"confirm": "COM"})
    assert trashed == ["F1"]


def test_with_drive_off_nothing_is_sent(app, client, monkeypatch):
    from app.db import get_db
    store, _ = _fake_drive(monkeypatch, app)
    app.config["FILE_STORE"] = "disk"
    u, p = make_department(app)
    login(client, u, p)
    j = client.post("/department/api/upload", data={
        "file": (io.BytesIO(_tiny_pdf()), "minutes.pdf"), "stage": "bos_documents", "field": "minutes",
    }, content_type="multipart/form-data").get_json()
    with app.app_context():
        assert "drive_id" not in get_db().files.find_one({"stored_name": j["stored"]})
    assert store == {}


def test_the_storage_page_shows_mongodb_drive_and_the_server(app, client, monkeypatch):
    from app import drive_store, storage_report
    store, _ = _fake_drive(monkeypatch, app)
    real = drive_store._call
    monkeypatch.setattr(drive_store, "_call", lambda payload, timeout=120, app=None: (
        {"ok": True, "root": "ROOT", "used": 5 * 1024 ** 3, "limit": 15 * 1024 ** 3}
        if payload["action"] == "ping" else real(payload, timeout, app)))
    storage_report._drive_cache.clear()
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/upload", data={
        "file": (io.BytesIO(_tiny_pdf()), "minutes.pdf"), "stage": "bos_documents", "field": "minutes",
    }, content_type="multipart/form-data")
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/storage").get_data(as_text=True)
    assert "MongoDB — typed answers" in page and "submissions" in page and "Total" in page
    assert "Google Drive — uploaded files" in page and "Connected" in page
    assert "drive.google.com/drive/folders/ROOT" in page
    assert "5.00 GB used of 15.00 GB" in page
    assert "Department of Commerce" in page and ">PDF<" in page
    assert "Server disk:" in page


def test_size_reads_in_words():
    from app.storage_report import size
    assert size(812) == "812 bytes" and size(2048) == "2.0 KB"
    assert size(38.4 * 1024 ** 2) == "38.4 MB" and size(1.25 * 1024 ** 3) == "1.25 GB"
