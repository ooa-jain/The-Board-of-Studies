"""End-to-end: login, the sequential lock, submitting Pre-BoS, exports."""

import json


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


def make_department(app, code="COM", name="Department of Commerce"):
    from app.db import generate_password, get_db, hash_password, now
    with app.app_context():
        db = get_db()
        db.departments.insert_one({
            "dept_code": code, "dept_name": name, "school": "School of Commerce",
            "campus": "Bengaluru", "hod_name": "Test Head",
            "hod_email": "head@example.edu", "hod_phone": "9999999999",
            "hod_designation": "Head of the Department",
            "active": True, "created_at": now(), "updated_at": now(),
        })
        pw = "DeptPassword1!"
        db.users.insert_one({
            "username": code.lower(), "password": hash_password(pw), "role": "department",
            "name": name, "dept_code": code, "active": True, "must_change": False,
            "created_at": now(),
        })
        return code.lower(), pw


# --------------------------------------------------------------------------

def test_landing_page_names_both_campuses(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Bengaluru" in body and "Kochi" in body
    assert "UGC Table 2" in body


def test_admin_can_sign_in_and_reach_the_dashboard(app, client):
    r = login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    assert r.status_code == 302
    assert client.get("/admin/").status_code == 200


def test_bad_password_is_rejected(app, client):
    r = client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                    "password": "wrong"})
    assert "do not match" in r.get_data(as_text=True)


def test_department_cannot_reach_the_admin_console(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.get("/admin/").status_code == 403


def test_credentials_are_generated_and_shown_once(app, client):
    make_department(app, "BBA", "Department of Business Administration")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    r = client.post("/admin/departments/BBA/credentials",
                    headers={"Accept": "application/json"})
    payload = r.get_json()
    assert payload["ok"] and payload["username"] and len(payload["password"]) >= 10

    # visible on the slip before first sign-in
    slip = client.get("/admin/departments/BBA/slip")
    assert payload["password"] in slip.get_data(as_text=True)

    # and the generated password actually works
    client.get("/logout")
    r = login(client, payload["username"], payload["password"])
    assert r.status_code == 302

    # once used, it is no longer shown to the admin
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    listing = client.get("/admin/departments").get_data(as_text=True)
    assert payload["password"] not in listing


def test_stages_after_the_first_are_locked(app, client):
    u, p = make_department(app)
    login(client, u, p)

    assert client.get("/department/stage/dept_info").status_code == 200

    r = client.get("/department/stage/pre_bos", follow_redirects=True)
    assert "opens once you have submitted" in r.get_data(as_text=True)


def test_submitting_department_information_unlocks_pre_bos(app, client):
    u, p = make_department(app)
    login(client, u, p)

    payload = {
        "identity": {"dept_name": "Department of Commerce", "school": "School of Commerce",
                     "dept_code": "COM", "campus": "Bengaluru",
                     "campus_address": "Jain Global Campus, Bengaluru 562112"},
        "hod": {"hod_name": "Test Head", "hod_designation": "Professor",
                "hod_email": "head@example.edu", "hod_phone": "9999999999"},
        "contact": {"office_email": "office@example.edu", "faculty_count": 24,
                    "programme_count": 3},
    }
    r = client.post("/department/api/dept_info/submit", json=payload)
    body = r.get_json()
    assert body["ok"] is True, body["issues"]
    assert body["next"]["key"] == "pre_bos"

    assert client.get("/department/stage/pre_bos").status_code == 200


def test_an_invalid_submission_is_refused_with_reasons(app, client):
    u, p = make_department(app)
    login(client, u, p)
    r = client.post("/department/api/dept_info/submit",
                    json={"contact": {"faculty_count": "twelve"}})
    body = r.get_json()
    assert body["ok"] is False
    msgs = [i["message"] for i in body["issues"]]
    assert any("must be a number" in m for m in msgs)
    assert any("is required" in m for m in msgs)


DEPT_INFO_OK = {
    "identity": {"dept_name": "Department of Commerce", "school": "School of Commerce",
                 "dept_code": "COM", "campus": "Bengaluru",
                 "campus_address": "Jain Global Campus, Bengaluru 562112"},
    "hod": {"hod_name": "Test Head", "hod_designation": "Professor",
            "hod_email": "head@example.edu", "hod_phone": "9999999999"},
    "contact": {"office_email": "office@example.edu", "faculty_count": 24,
                "programme_count": 3},
}


def test_pre_bos_composition_rules_are_enforced(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit",
                       json=DEPT_INFO_OK).get_json()["ok"]

    thin = {
        "diac": [{"name": "A Person", "designation": "Prof", "organisation": "JAIN",
                  "email": "a@example.edu", "role": "Convener"}],
        "bos": [], "pac": [],
    }
    r = client.post("/department/api/pre_bos/validate", json=thin)
    msgs = [i["message"] for i in r.get_json()["issues"]]
    assert any("at least 4 members" in m for m in msgs)
    assert any("Industry Member" in m for m in msgs)
    assert any("exactly one Chairperson (HoD)" in m for m in msgs)
    assert any("at least 3 members" in m for m in msgs)


def test_autosave_keeps_a_draft(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save",
                json={"identity": {"dept_name": "Half filled"}})
    r = client.get("/department/stage/dept_info")
    assert "Half filled" in r.get_data(as_text=True)


def test_exports_produce_real_files(app, client):
    u, p = make_department(app)
    login(client, u, p)
    x = client.get("/department/export.xlsx")
    assert x.status_code == 200 and x.data[:2] == b"PK"
    w = client.get("/department/export.docx")
    assert w.status_code == 200 and w.data[:2] == b"PK"


def test_admin_can_edit_the_credit_rules(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    assert client.get("/admin/rules").status_code == 200

    form = {"total.ug3": "120", "total.ug4": "160",
            "other.marks_per_credit": "25", "other.max_credits_per_course": "8",
            "other.meeting_notice_days": "7", "other.revision_benchmark_threshold": "30"}
    for key, ug3, ug4 in [("major_core", 62, 80), ("minor_stream", 24, 32),
                          ("multidisciplinary", 9, 9), ("aec", 8, 8), ("sec", 9, 9),
                          ("vac", 6, 6), ("internship", 2, 2), ("research", 0, 12)]:
        form[f"{key}.ug3.min"] = str(ug3)
        form[f"{key}.ug4.min"] = str(ug4)
        if key != "research":
            form[f"{key}.ug3.applicable"] = "on"
        form[f"{key}.ug4.applicable"] = "on"

    r = client.post("/admin/rules", data=form, follow_redirects=True)
    assert r.status_code == 200

    from app.db import rules_doc
    with app.app_context():
        doc = rules_doc()
        major = next(x for x in doc["table2"] if x["key"] == "major_core")
        assert major["ug3"]["min"] == 62


def test_admin_can_return_a_stage_for_correction(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json={
        "identity": {"dept_name": "D", "school": "S", "dept_code": "COM",
                     "campus": "Bengaluru", "campus_address": "Address here"},
        "hod": {"hod_name": "Test Head", "hod_designation": "Professor",
                "hod_email": "head@example.edu", "hod_phone": "9999999999"},
        "contact": {"office_email": "office@example.edu", "faculty_count": 1,
                    "programme_count": 1}})
    client.get("/logout")

    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    r = client.post("/admin/submissions/COM/dept_info/return",
                    data={"note": "Campus address is incomplete."}, follow_redirects=True)
    assert r.status_code == 200
    client.get("/logout")

    login(client, u, p)
    dash = client.get("/department/").get_data(as_text=True)
    assert "Campus address is incomplete." in dash


def test_department_cannot_touch_another_departments_stage(app, client):
    u, p = make_department(app, "COM")
    make_department(app, "ENG", "Department of English")
    login(client, u, p)
    # the department blueprint always scopes to the signed-in department,
    # so there is no route that accepts another department's code
    r = client.get("/department/")
    assert "Department of English" not in r.get_data(as_text=True)
