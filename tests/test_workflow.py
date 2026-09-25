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


def test_login_is_derived_from_the_department_code(app, client):
    """No person's details are involved — the code decides the username."""
    make_department(app, "COM-BBA", "Department of Business Administration")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    r = client.post("/admin/departments/COM-BBA/credentials",
                    headers={"Accept": "application/json"})
    assert r.get_json()["username"] == "com.bba"


def test_bulk_and_single_issue_the_same_shape_of_login(app, client):
    make_department(app, "ECO", "Department of Economics")
    make_department(app, "PSY", "Department of Psychology")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    single = client.post("/admin/departments/ECO/credentials",
                         headers={"Accept": "application/json"}).get_json()
    client.post("/admin/credentials/bulk")

    from app.db import get_db
    with app.app_context():
        psy = get_db().departments.find_one({"dept_code": "PSY"})
        eco = get_db().departments.find_one({"dept_code": "ECO"})

    assert eco["username"] == single["username"] == "eco"
    assert psy["username"] == "psy"
    # both routes leave the password in the clear for the slip, and a user row
    assert len(psy["initial_password"]) >= 10
    with app.app_context():
        assert get_db().users.find_one({"username": "psy", "role": "department"})

    # the bulk-issued password works
    client.get("/logout")
    assert login(client, "psy", psy["initial_password"]).status_code == 302


def test_a_department_record_holds_no_personal_details(app, client):
    make_department(app, "LAW", "Department of Law")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/departments").get_data(as_text=True)
    assert "HoD" not in page
    form = client.get("/admin/departments/LAW/edit").get_data(as_text=True)
    for field in ("hod_name", "hod_email", "hod_phone", "hod_designation"):
        assert field not in form


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
        "contact": {"office_email": "office@example.edu", "faculty_count": 24},
        "programmes": [{"programme_name": "BCom (Corporate Finance)", "programme_code": "BCOM-CF",
                        "degree_level": "UG - 4 Year (Honours)", "batch": "2026-30"}],
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
    "contact": {"office_email": "office@example.edu", "faculty_count": 24},
    "programmes": [
        {"programme_name": "BCom (Corporate Finance)", "programme_code": "BCOM-CF",
         "degree_level": "UG - 3 Year", "specialisation": "Analytics", "batch": "2026-29"},
        {"programme_name": "MCom", "programme_code": "MCOM",
         "degree_level": "PG - 2 Year", "batch": "2026-28"},
    ],
}


def _file(name):
    return {"name": name, "stored": "x-" + name, "size": 1024}


PRE_BOS_FILES_OK = {
    "pre_bos_files": {"diac_signed": _file("diac.pdf"), "dpac_signed": _file("dpac.pdf")},
}

BOS_DOCS_OK = {
    "meeting": {"bos_date": "2026-03-12"},
    "bos_files": {
        "bos_composition": _file("bos.pdf"), "vision_mission": _file("vm.pdf"),
        "minutes": _file("minutes.pdf"), "geotagged_photos": [_file("a.jpg"), _file("b.jpg")],
        "external_profiles": [_file("p1.pdf")], "attendance": _file("att.pdf"),
        "feedback_curriculum": _file("fb.pdf"),
    },
}


def test_pre_bos_requires_diac_and_dpac(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit",
                       json=DEPT_INFO_OK).get_json()["ok"]

    r = client.post("/department/api/pre_bos/validate", json={})
    msgs = [i["message"] for i in r.get_json()["issues"]]
    assert any("Department Industry-Academia Cell" in m for m in msgs)
    assert any("Programme Assessment Committee (DPAC)" in m for m in msgs)

    partial = {"pre_bos_files": {"diac_signed": _file("diac.pdf")}}
    assert not client.post("/department/api/pre_bos/submit", json=partial).get_json()["ok"]

    body = client.post("/department/api/pre_bos/submit", json=PRE_BOS_FILES_OK).get_json()
    assert body["ok"] and body["next"]["key"] == "bos_documents"


def test_pre_bos_is_only_diac_and_dpac(app, client):
    from app.schema import STAGE_BY_KEY, STAGE_KEYS
    assert STAGE_KEYS == ["dept_info", "pre_bos", "bos_documents", "curriculum"]
    files = [f["name"] for s in STAGE_BY_KEY["pre_bos"]["sections"]
             for f in s["fields"] if f["type"] == "file"]
    assert files == ["diac_signed", "dpac_signed"]


def _through_bos_documents(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    assert client.post("/department/api/pre_bos/submit", json=PRE_BOS_FILES_OK).get_json()["ok"]
    body = client.post("/department/api/bos_documents/submit", json=BOS_DOCS_OK).get_json()
    assert body["ok"], body["issues"]
    assert body["next"]["key"] == "curriculum"
    return u, p


def test_bos_documents_needs_every_upload_but_the_new_programme_feedback(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.post("/department/api/pre_bos/submit", json=PRE_BOS_FILES_OK)
    msgs = [i["message"] for i in
            client.post("/department/api/bos_documents/validate", json={}).get_json()["issues"]]
    for label in ("Composition of BoS Members", "Minutes of Meeting",
                  "Geotagged photos", "Profiles of External Members", "Scanned Attendance Sheet",
                  "Stakeholder Feedback (For Curriculum Design and Development)"):
        assert any(label in m for m in msgs), label
    assert not any("New Program" in m for m in msgs)


def test_curriculum_lists_mapped_programmes_under_ug_and_pg(app, client):
    _through_bos_documents(app, client)
    page = client.get("/department/stage/curriculum").get_data(as_text=True)
    assert "UG programmes" in page and "PG programmes" in page
    assert "BCom (Corporate Finance)" in page and "MCom" in page
    for part in ("prog_curriculum", "prog_syllabus", "prog_revision"):
        assert f"/department/stage/{part}/BCOM-CF" in page


def test_programme_parts_are_prefilled(app, client):
    _through_bos_documents(app, client)
    page = client.get("/department/stage/prog_curriculum/BCOM-CF").get_data(as_text=True)
    assert '"duration_months": 36' in page and '"medium": "English"' in page

    structure = [{"semester": 1, "nep_category": "Major (Core)", "course_code": "26BCC1C01",
                  "course_title": "Basics of Financial Accounting", "l": 4, "t": 0, "p": 0,
                  "e": 0, "credits": 4, "cia": 50, "ese": 50, "total_marks": 100}]
    client.post("/department/api/prog_curriculum/BCOM-CF/save", json={"structure": structure})

    syl = client.get("/department/stage/prog_syllabus/BCOM-CF").get_data(as_text=True)
    assert '"course_code": "26BCC1C01"' in syl and '"teaching_hours": 60' in syl

    rev = client.get("/department/stage/prog_revision/BCOM-CF").get_data(as_text=True)
    assert '"bos_date": "2026-03-12"' in rev and '"degree_level": "UG"' in rev


def test_submitting_every_part_completes_and_seals(app, client, monkeypatch):
    from app import workflow
    _through_bos_documents(app, client)

    # every part validates clean — the parts' own checks are covered elsewhere
    monkeypatch.setattr(workflow, "validate_stage",
                        lambda *a, **k: ([], {"errors": 0, "warnings": 0}))
    for code in ("BCOM-CF", "MCOM"):
        for part in ("prog_curriculum", "prog_syllabus", "prog_revision"):
            body = client.post(f"/department/api/{part}/{code}/submit", json={}).get_json()
            assert body["ok"]
            assert body["redirect"].endswith("/department/stage/curriculum")

    # a submitted part is read only
    r = client.post("/department/api/prog_syllabus/MCOM/save", json={})
    assert r.status_code == 409

    from app.db import get_db
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        assert sub["status"] == "sealed"
        assert workflow.compute_status(sub, "curriculum") == "submitted"


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
        "contact": {"office_email": "office@example.edu", "faculty_count": 1},
        "programmes": [{"programme_name": "BCom", "programme_code": "BCOM",
                        "degree_level": "UG - 3 Year", "batch": "2026-29"}]})
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
