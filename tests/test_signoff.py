"""HoD / Dean sign-off: the Head of the Department, then the Dean, approves
before the final submit; it is printed in the documents; a stage sent back
clears it."""

import io

from test_workflow import approve_both, login, make_department


def _admin(app, client):
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_hod_first_then_dean_and_withdraw(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    rec = client.get("/department/api/record").get_json()
    roles = [a["role"] for a in rec["signoff"]["approvers"]]
    assert roles == ["hod", "dean"] and rec["signoff"]["approvers"][0]["name"] == "Test Head"

    r = client.post("/department/api/approve", json={"role": "dean", "name": "Dr. Dean"}).get_json()
    assert not r["ok"] and "first" in r["error"]
    assert not client.post("/department/api/approve", json={"role": "hod", "name": "x"}).get_json()["ok"]

    r = client.post("/department/api/approve", json={"role": "hod", "name": "Dr. Test Head"}).get_json()
    assert r["ok"] and r["signoff"]["approvers"][0]["approved"] and r["signoff"]["approvers"][0]["at"]
    r = client.post("/department/api/approve", json={"role": "dean", "name": "Dr. Dean"}).get_json()
    assert r["ok"] and r["signoff"]["approvers"][1]["approved"]
    # withdrawing the HoD's takes the Dean's with it
    r = client.post("/department/api/approve/withdraw", json={"role": "hod"}).get_json()
    assert r["ok"] and not any(a["approved"] for a in r["signoff"]["approvers"])
    with app.app_context():
        assert not get_db().submissions.find_one({"dept_code": "COM"}).get("approvals")


def test_signoff_is_printed_and_cleared_when_sent_back(app, client):
    from docx import Document

    from app import demo_dept
    from app.db import get_db
    from app.docgen import curriculum_docx
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    approve_both(client, hod="Dr. Anita Rao", dean="Dr. Vikram Shah")
    assert client.post("/department/api/submit-all").get_json()["ok"]
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "DEMO"})
        assert sub["status"] == "sealed"
        doc = Document(io.BytesIO(curriculum_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Head of the Department: Dr. Anita Rao — approved" in text and "Dean: Dr. Vikram Shah" in text

    _admin(app, client)
    client.post("/admin/submissions/DEMO/pre_bos/return", data={"note": "Fix the DPAC file"})
    with app.app_context():
        assert not get_db().submissions.find_one({"dept_code": "DEMO"}).get("approvals")
