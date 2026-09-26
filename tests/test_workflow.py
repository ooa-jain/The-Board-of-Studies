"""End-to-end: login, the sequential lock, submitting Pre-BoS, exports."""

import json


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


def make_department(app, code="COM", name="Department of Commerce",
                    school="School of Commerce"):
    from app.db import generate_password, get_db, hash_password, now
    with app.app_context():
        db = get_db()
        db.departments.insert_one({
            "dept_code": code, "dept_name": name, "school": school,
            "campus": "Jain Global Campus", "hod_name": "Test Head",
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


# Department Information → Programmes offered: one kept from the workbook,
# one dropped, one the department added.
PROGRAMMES_OK = [
    {"programme_code": "BCMREG", "programme_name": "Bachelor of Commerce", "degree": "UG",
     "source": "catalogue", "decision": "keep"},
    {"programme_code": "BCHCOF", "programme_name": "B.Com in Corporate Finance",
     "degree": "UG", "source": "catalogue", "decision": "remove",
     "removal_reason": "Programme discontinued"},
    {"programme_code": "MCMNEW", "programme_name": "Master of Commerce", "degree": "PG",
     "source": "new", "decision": "keep"},
]


# --------------------------------------------------------------------------

def test_landing_page_does_not_name_the_campuses(client):
    """The home page speaks for the university, not for one campus or two."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Kochi" not in body
    assert "Bengaluru" not in body
    assert "Bangalore" not in body
    # but it still explains what the portal is for
    assert "Board of Studies" in body
    # the credit-rules showcase was taken off the home page
    assert "The checking" not in body and "UGC Table 2" not in body


def test_seed_list_is_usable_as_a_department_master(app):
    """A submission hangs off the code, so no two records may share one."""
    from seed import SEED_DEPARTMENTS
    codes = [c for *_, c in SEED_DEPARTMENTS]

    assert len(codes) == len(set(codes)), "duplicate department code"
    assert all(codes), "every department needs a code"
    for faculty, school, name, place, campus, code in SEED_DEPARTMENTS:
        assert faculty and school and name and place and campus, code
        # the same department at a second campus is a second record, and the
        # pair is what has to be unique, not the name
        assert campus.strip() == campus

    # a department can sit under two schools at one campus (Management Studies
    # does), so the triple is what has to be unique, not the pair
    triples = [(n, s, c) for _, s, n, _, c, _ in SEED_DEPARTMENTS]
    assert len(triples) == len(set(triples)), "the same record twice"


def test_seed_matches_the_workbook(app):
    """The counts the workbook actually contains, so a bad edit is caught."""
    from seed import SEED_DEPARTMENTS
    assert len(SEED_DEPARTMENTS) == 54
    assert len({d for _, _, d, _, _, _ in SEED_DEPARTMENTS}) == 30
    assert len({s for _, s, _, _, _, _ in SEED_DEPARTMENTS}) == 13
    assert len({f for f, _, _, _, _, _ in SEED_DEPARTMENTS}) == 6
    assert {p for _, _, _, p, _, _ in SEED_DEPARTMENTS} == {"Bangalore", "Kochi"}
    # nothing about a person belongs in the department master
    flat = " ".join(" ".join(r) for r in SEED_DEPARTMENTS).lower()
    for word in ("dr.", "director", "hod", "dean", "@"):
        assert word not in flat, f"{word!r} leaked into the department list"


def test_admin_can_sign_in_and_reach_the_dashboard(app, client):
    r = login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    assert r.status_code == 302
    assert client.get("/admin/").status_code == 200


def test_bad_password_is_rejected(app, client):
    """The form is on the home page, so the refusal goes back to it."""
    r = client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                    "password": "wrong"})
    assert r.status_code == 302 and r.headers["Location"].endswith("#signin")
    assert "do not match" in client.get("/").get_data(as_text=True)


def test_there_is_no_separate_login_page(app, client):
    """A GET lands on the form rather than on a second copy of it."""
    r = client.get("/login")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("#signin")

    # and being sent here by a guard keeps where you were going
    r = client.get("/department/", follow_redirects=False)
    assert "/login?next=/department/" in r.headers["Location"]
    r = client.get(r.headers["Location"], follow_redirects=False)
    assert "next=/department/" in r.headers["Location"]
    assert 'name="next" value="/department/"' in client.get(
        r.headers["Location"]).get_data(as_text=True)


def test_signing_in_lands_where_you_were_going(app, client):
    u, p = make_department(app)
    r = client.post("/login", data={"username": u, "password": p,
                                    "next": "/department/stage/dept_info"})
    assert r.headers["Location"].endswith("/department/stage/dept_info")


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


def test_login_is_department_school_and_a_number(app, client):
    """No person's details are involved: the department and its school decide
    the name, and a number keeps two campuses of one department apart."""
    import re

    make_department(app, "BBA-JYN", "Department of Business Administration")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    r = client.post("/admin/departments/BBA-JYN/credentials",
                    headers={"Accept": "application/json"})
    username = r.get_json()["username"]
    assert re.fullmatch(r"ba\.sc\.\d{4}", username), username


def test_two_campuses_of_one_department_get_different_logins(app, client):
    from app.db import get_db
    school = "School of Computer Science and Engineering"
    make_department(app, "CSE-JGC", "Department of Computer Science and Engineering", school)
    make_department(app, "CSE-KCH", "Department of Computer Science and Engineering", school)
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    client.post("/admin/credentials/bulk")
    with app.app_context():
        names = [d["username"] for d in get_db().departments.find(
            {"dept_code": {"$in": ["CSE-JGC", "CSE-KCH"]}})]
    assert len(names) == 2 and names[0] != names[1], names
    assert all(n.startswith("cse.scse.") for n in names), names


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

    import re

    assert eco["username"] == single["username"]
    for d in (eco, psy):
        assert re.fullmatch(r"[a-z]+\.[a-z]+\.\d{4}", d["username"]), d["username"]
    # both routes leave the password in the clear for the slip, and a user row
    assert len(psy["initial_password"]) >= 10
    with app.app_context():
        assert get_db().users.find_one({"username": psy["username"],
                                        "role": "department"})

    # the bulk-issued password works
    client.get("/logout")
    assert login(client, psy["username"], psy["initial_password"]).status_code == 302


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
                     "dept_code": "COM", "campus": "Jain Global Campus"},
        "hod": {"hod_name": "Test Head", "hod_designation": "Professor",
                "hod_email": "head@example.edu", "hod_phone": "9999999999"},
        "contact": {"office_email": "office@example.edu", "faculty_count": 24},
        "programmes_offered": PROGRAMMES_OK,
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
                    json={"identity": {"dept_name": ""}, "programmes_offered": []})
    body = r.get_json()
    assert body["ok"] is False
    msgs = [i["message"] for i in body["issues"]]
    assert any("is required" in m for m in msgs)
    assert any("at least one programme" in m for m in msgs)


DEPT_INFO_OK = {
    "identity": {"dept_name": "Department of Commerce", "school": "School of Commerce",
                 "dept_code": "COM", "campus": "Jain Global Campus"},
    "contact": {"office_email": "office@example.edu", "faculty_count": 24},
    "programmes_offered": PROGRAMMES_OK,
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


def test_the_four_stages_in_order(app):
    from app.schema import STAGE_BY_KEY, STAGE_KEYS
    assert STAGE_KEYS == ["dept_info", "pre_bos", "bos_documents", "curriculum"]
    files = [f["name"] for s in STAGE_BY_KEY["pre_bos"]["sections"]
             for f in s["fields"] if f["type"] == "file"]
    assert files == ["diac_signed", "dpac_signed"]
    assert STAGE_BY_KEY["curriculum"]["parts"] == ["prog_curriculum", "prog_syllabus",
                                                   "prog_revision"]


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


def test_curriculum_lists_the_programmes_kept_under_ug_and_pg(app, client):
    _through_bos_documents(app, client)
    page = client.get("/department/stage/curriculum").get_data(as_text=True)
    assert "UG programmes" in page and "PG programmes" in page
    assert "Bachelor of Commerce" in page and "Master of Commerce" in page
    # the programme removed in Department Information is not offered
    assert "BCHCOF" not in page
    for part in ("prog_curriculum", "prog_syllabus", "prog_revision"):
        assert f"/department/stage/{part}/BCMREG" in page


def _stage_data(body):
    return json.loads(body.split('id="stage-data" type="application/json">')[1]
                      .split("</script>")[0])


def test_programme_parts_are_prefilled(app, client):
    _through_bos_documents(app, client)
    data = _stage_data(client.get("/department/stage/prog_curriculum/MCMNEW")
                       .get_data(as_text=True))
    assert data["details"]["programme_name"] == "Master of Commerce"
    assert data["details"]["degree_level"] == "PG - 2 Year"
    assert data["profile"]["medium"] == "English"

    client.post("/department/api/prog_curriculum/BCMREG/save", json={
        "details": {"degree_level": "UG - 3 Year", "batch": "2026-29"},
        "semester_structure": [{"semester": 1, "nep_category": "Major (Core)",
                                "course_code": "26BCC1C01",
                                "course_title": "Basics of Financial Accounting",
                                "l": 4, "t": 0, "p": 0, "e": 0, "credits": 4,
                                "cia": 50, "ese": 50, "total_marks": 100}]})

    syl = client.get("/department/stage/prog_syllabus/BCMREG").get_data(as_text=True)
    fill = json.loads(syl.split("fill: ")[1].split(",\n")[0])
    assert fill == [{"course_code": "26BCC1C01", "course_title": "Basics of Financial Accounting",
                     "semester": 1, "credits": 4, "year_latest": "2026",
                     "hours_per_week": 4, "teaching_hours": 60}]
    assert _stage_data(syl)["header"]["batch"] == "2026-29"

    rev = _stage_data(client.get("/department/stage/prog_revision/BCMREG").get_data(as_text=True))
    assert rev["header"]["bos_date"] == "2026-03-12"
    assert rev["header"]["degree_level"] == "UG"


def test_submitting_every_part_completes_and_seals(app, client, monkeypatch):
    from app import workflow
    _through_bos_documents(app, client)

    # every part validates clean — the parts' own checks are covered elsewhere
    monkeypatch.setattr(workflow, "validate_stage",
                        lambda *a, **k: ([], {"errors": 0, "warnings": 0}))
    for code in ("BCMREG", "MCMNEW"):
        for part in ("prog_curriculum", "prog_syllabus", "prog_revision"):
            body = client.post(f"/department/api/{part}/{code}/submit", json={}).get_json()
            assert body["ok"]
            assert body["redirect"].endswith("/department/stage/curriculum")

    # a submitted part is read only
    assert client.post("/department/api/prog_syllabus/MCMNEW/save", json={}).status_code == 409

    from app.db import get_db
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        assert sub["status"] == "sealed"
        assert workflow.compute_status(sub, "curriculum") == "submitted"


def test_returning_the_curriculum_sends_every_part_back(app, client, monkeypatch):
    from app import workflow
    u, p = _through_bos_documents(app, client)
    monkeypatch.setattr(workflow, "validate_stage",
                        lambda *a, **k: ([], {"errors": 0, "warnings": 0}))
    client.post("/department/api/prog_syllabus/BCMREG/submit", json={})
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    client.post("/admin/submissions/COM/curriculum/return", data={"note": "Fix the books."})
    client.get("/logout")
    login(client, u, p)
    page = client.get("/department/stage/curriculum").get_data(as_text=True)
    assert "Returned: Fix the books." in page


def test_submitting_a_stage_carries_you_into_the_next_one(app, client):
    """The point of the automation: no going back to the list to find it."""
    u, p = make_department(app)
    login(client, u, p)
    r = client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()
    assert r["ok"]
    assert r["next"]["key"] == "pre_bos"
    assert r["redirect"].endswith("/department/stage/pre_bos")

    # and the next one carries on from there
    r = client.post("/department/api/pre_bos/submit", json=PRE_BOS_FILES_OK).get_json()
    assert r["ok"]
    assert r["redirect"].endswith(f"/department/stage/{r['next']['key']}")


def test_the_dashboard_names_the_next_step(app, client):
    u, p = make_department(app)
    login(client, u, p)
    body = client.get("/department/").get_data(as_text=True)
    assert "Next Stage" in body
    assert "Department Information" in body

    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    body = client.get("/department/").get_data(as_text=True)
    assert "Pre-BoS" in body


def test_next_action_prefers_a_returned_stage(app):
    """A stage sent back for correction outranks anything merely open."""
    from app.workflow import next_action, get_or_create_submission
    from app.db import get_db
    make_department(app)
    with app.app_context():
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": {
            "stages.dept_info.status": "submitted",
            "stages.pre_bos.status": "draft",
            "stages.bos_documents.status": "returned",
        }})
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        nxt = next_action(sub)
        assert nxt["key"] == "bos_documents"
        assert nxt["status"] == "returned"


def test_next_action_is_none_once_everything_is_submitted(app):
    from app.workflow import next_action, get_or_create_submission
    from app.db import get_db
    from app.schema import STAGE_KEYS
    make_department(app)
    with app.app_context():
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        # the Curriculum is done when every part of every programme is
        update = {f"stages.{k}.status": "submitted" for k in STAGE_KEYS[:-1]}
        update["stages.dept_info.data"] = {"programmes_offered": PROGRAMMES_OK}
        for code in ("BCMREG", "MCMNEW"):
            for part in ("prog_curriculum", "prog_syllabus", "prog_revision"):
                update[f"programmes.{code}.{part}.status"] = "submitted"
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": update})
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        assert next_action(sub) is None


def test_autosave_keeps_a_draft(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save",
                json={"identity": {"dept_name": "Half filled"}})
    r = client.get("/department/stage/dept_info")
    assert "Half filled" in r.get_data(as_text=True)


def test_exports_produce_real_files(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)

    # not before the record is finished — and not offered in the bar either
    r = client.get("/department/export.xlsx")
    assert r.status_code == 302 and r.headers["Location"].endswith("/department/")
    body = client.get("/department/").get_data(as_text=True)
    assert "export.xlsx" not in body and "export.docx" not in body

    with app.app_context():
        get_db().submissions.update_one({"dept_code": "COM"}, {"$set": {"status": "sealed"}})
    assert "export.xlsx" in client.get("/department/").get_data(as_text=True)
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
                     "campus": "Jain Global Campus"},
        "hod": {"hod_name": "Test Head", "hod_designation": "Professor",
                "hod_email": "head@example.edu", "hod_phone": "9999999999"},
        "contact": {"office_email": "office@example.edu", "faculty_count": 1},
        "programmes_offered": PROGRAMMES_OK})
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


def test_the_stage_side_menu_branches_by_group(app, client):
    """The side menu groups the thirteen stages, and renders them.

    Asserting on the titles matters as much as on the groups: the group dict
    is walked in the template, and a mis-named key there fails silently by
    rendering an empty menu rather than by raising.
    """
    from html import escape

    from app.schema import STAGES
    u, p = make_department(app)
    login(client, u, p)
    body = client.get("/department/stage/dept_info").get_data(as_text=True)

    groups = []
    for s in STAGES:
        if s["group"] not in groups:
            groups.append(s["group"])
    # a group heading appearing twice with other groups in between would give
    # the menu two branches of the same name
    assert len(groups) == len(set(groups)), "group names have to be unique"
    for g in groups:
        assert f'<span class="branch-label">{escape(g)}</span>' in body, g
    for s in STAGES:
        assert escape(s["title"]) in body, s["title"]

    # the group you are in is the open one, and the rest are folded
    assert body.count('data-open="true"') == 1
    assert body.count('data-open="false"') == len(groups) - 1

    # the stage being filled is marked, and a locked stage is not a link
    assert 'class="branch-row is-open is-here"' in body
    assert 'class="branch-row is-locked"' in body


def test_grouped_board_counts_each_group(app):
    from app.db import get_db
    from app.workflow import get_or_create_submission, grouped_board, stage_board
    make_department(app)
    with app.app_context():
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": {
            "stages.dept_info.status": "submitted"}})
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])

        groups = grouped_board(stage_board(sub))
        assert [g["name"] for g in groups][0] == "Level 0 · Department"
        assert groups[0]["done"] == groups[0]["total"] and groups[0]["complete"]
        assert groups[1]["done"] == 0 and not groups[1]["complete"]
        assert sum(g["total"] for g in groups) == len(stage_board(sub))


def test_the_home_page_carries_the_loading_screen(client):
    """It is inert markup until the page's own script reveals it."""
    body = client.get("/").get_data(as_text=True)
    assert 'id="preload-canvas"' in body
    assert "is-preloading" in body
    assert "js/particle-text.js" in body
    # and it never appears on a page a department is working in
    assert 'id="preload-canvas"' not in client.get("/login").get_data(as_text=True)


def test_the_portal_is_named_ooa_data_portal(client):
    body = client.get("/").get_data(as_text=True)
    assert "BoS Academic Portal" in body
    assert "BoS Data Repository" not in body


def test_admin_can_filter_departments_by_city(app, client):
    from app.db import get_db, now
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    with app.app_context():
        get_db().departments.insert_many([
            {"dept_code": "AAA", "dept_name": "Alpha", "school": "School of A",
             "place": "Bangalore", "campus": "Jayanagar Campus", "active": True,
             "created_at": now(), "updated_at": now()},
            {"dept_code": "BBB", "dept_name": "Beta", "school": "School of B",
             "place": "Kochi", "campus": "Kochi Campus", "active": True,
             "created_at": now(), "updated_at": now()},
        ])

    both = client.get("/admin/departments").get_data(as_text=True)
    assert "Alpha" in both and "Beta" in both

    blr = client.get("/admin/departments?place=Bangalore").get_data(as_text=True)
    assert "Alpha" in blr and "Beta" not in blr
    # and the campus row only offers campuses that city has
    assert "Jayanagar Campus" in blr and "Kochi Campus" not in blr

    kochi = client.get("/admin/departments?place=Kochi").get_data(as_text=True)
    assert "Beta" in kochi and "Alpha" not in kochi


def test_clearing_the_master_needs_the_words(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    # a bare post does nothing
    client.post("/admin/departments/clear", data={"confirm": "yes"})
    with app.app_context():
        assert get_db().departments.count_documents({}) == 1

    client.post("/admin/departments/clear", data={"confirm": "remove all"})
    with app.app_context():
        db = get_db()
        assert db.departments.count_documents({}) == 0
        assert db.users.count_documents({"role": "department"}) == 0
        # the admin is not a department, and stays
        assert db.users.count_documents({"role": "admin"}) == 1


def test_the_not_found_page_offers_a_way_onward(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    body = r.get_data(as_text=True)
    assert "There is no page here" in body
    assert "About the portal" in body and "The home page" in body


def _tiny_pdf():
    """A valid one-page PDF, built here so the test needs no fixture file."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"]
    stream = "BT /F1 24 Tf 60 760 Td (DIAC Composition) Tj ET\n"
    objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}endstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _upload(client, name, data):
    import io
    return client.post("/department/api/upload", data={
        "file": (io.BytesIO(data), name), "stage": "pre_bos", "field": "diac_file",
    }, content_type="multipart/form-data").get_json()


def test_a_pdf_upload_is_given_a_picture_of_its_first_page(app, client):
    u, p = make_department(app)
    login(client, u, p)

    j = _upload(client, "diac.pdf", _tiny_pdf())
    assert j["ok"] and j["thumb"], j
    r = client.get(j["thumb"])
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/png"
    assert r.get_data()[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"

    # drawn once, then kept: the second request is served from the same file
    assert client.get(j["thumb"]).status_code == 200


def test_a_word_upload_has_no_picture_and_does_not_pretend_to(app, client):
    u, p = make_department(app)
    login(client, u, p)

    j = _upload(client, "minutes.docx", b"PK\x03\x04 not really a docx")
    assert j["ok"]
    assert j["thumb"] is None, "only a PDF can be drawn"
    assert client.get(j["url"] + "?thumb=1").status_code == 404


def test_files_download_unless_the_page_asks_to_show_them(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "diac.pdf", _tiny_pdf())

    plain = client.get(j["url"])
    assert "attachment" in plain.headers["Content-Disposition"]

    shown = client.get(j["url"] + "?inline=1")
    assert "attachment" not in shown.headers.get("Content-Disposition", "")

    # a Word file is never handed over to be displayed: the browser would only
    # offer to download it again, under a worse name
    w = _upload(client, "minutes.docx", b"PK\x03\x04")
    assert "attachment" in client.get(w["url"] + "?inline=1").headers["Content-Disposition"]


def test_a_signed_in_department_is_not_asked_to_sign_in_again(app, client):
    u, p = make_department(app)
    login(client, u, p)
    body = client.get("/").get_data(as_text=True)

    assert 'name="password"' not in body, "the home page still asks for a password"
    assert "Sign out" in body
    assert ">Home</a>" in body, "no way back to the home page from the bar"
    # and it shows where they had got to
    assert "0 of 4 stages completed" in body
    assert "Next Stage" in body and "Department Information" in body

    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    body = client.get("/").get_data(as_text=True)
    assert "1 of 4 stages completed" in body
    assert "Pre-BoS" in body


def test_the_admin_gets_the_console_not_a_department_panel(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    body = client.get("/").get_data(as_text=True)
    assert 'name="password"' not in body
    assert "The admin dashboard" in body
    assert "stages completed" not in body


def test_the_analysis_tells_each_department_apart(app, client):
    """Six states, and they must not be confused with one another."""
    from app.db import get_db, now
    from app.schema import STAGE_KEYS

    make_department(app, "AAA", "Alpha")          # login, never signed in
    make_department(app, "BBB", "Beta")           # will sign in and file
    make_department(app, "CCC", "Gamma")          # login, signed in, nothing filed
    with app.app_context():
        db = get_db()
        db.departments.insert_one({"dept_code": "DDD", "dept_name": "Delta",
                                   "school": "School of D", "campus": "Kochi Campus",
                                   "active": True, "created_at": now(),
                                   "updated_at": now()})   # no login at all
        db.users.update_one({"username": "ccc"}, {"$set": {"last_login": now()}})

    u, p = "bbb", "DeptPassword1!"
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.get("/logout")

    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    body = client.get("/admin/analysis").get_data(as_text=True)

    assert "No login issued" in body      # Delta
    assert "Never signed in" in body      # Alpha
    assert "In progress" in body          # Beta
    assert "Signed in, nothing filed" in body   # Gamma

    # and the filters cut it down without changing the totals
    only = client.get("/admin/analysis?state=never_in").get_data(as_text=True)
    assert "Alpha" in only and "Beta" not in only


def test_the_analysis_counts_the_whole_institution(app):
    from app.workflow import (department_analysis, get_or_create_submission,
                              institution_analysis)
    from app.db import get_db, now
    make_department(app, "AAA", "Alpha")
    make_department(app, "BBB", "Beta")
    with app.app_context():
        db = get_db()
        year = app.config["ACADEMIC_YEAR"]
        sub = get_or_create_submission("AAA", year)
        db.submissions.update_one({"_id": sub["_id"]}, {"$set": {
            "stages.dept_info.status": "submitted",
            "stages.pre_bos.status": "draft",
            "stages.pre_bos.summary": {"errors": 2, "warnings": 1},
        }})
        db.users.update_one({"username": "aaa"}, {"$set": {"last_login": now()}})

        rows = []
        for code in ("AAA", "BBB"):
            d = db.departments.find_one({"dept_code": code})
            rows.append(department_analysis(
                d, get_or_create_submission(code, year),
                db.users.find_one({"dept_code": code})))

    alpha = next(r for r in rows if r["dept"]["dept_code"] == "AAA")
    assert alpha["done"] == 1 and alpha["half"] == 1 and alpha["errors"] == 2
    assert alpha["state"] == "in_progress"
    assert alpha["next"]["key"] == "pre_bos", "the half-filled stage is what is next"

    totals = institution_analysis(rows)
    assert totals["departments"] == 2
    assert totals["stages_done"] == 1
    assert totals["half_filled"] == 1
    assert totals["errors"] == 2
    assert totals["with_errors"] == 1
    assert totals["never_in"] == 1, "Beta has a login but has never used it"


def test_the_demo_tab_is_made_up_and_says_so(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    live = client.get("/admin/analysis").get_data(as_text=True)
    assert "made-up departments" not in live, "the live tab must never carry the banner"

    demo = client.get("/admin/analysis?demo=1").get_data(as_text=True)
    assert "These are made-up departments" in demo
    assert "Switch to live data" in demo
    # it fills the screen, and nothing it shows came from the database
    assert demo.count('class="an-') > 10
    with_db = client.get("/admin/analysis").get_data(as_text=True)
    assert "Department of Computer Science and Engineering" not in with_db


def test_the_demo_numbers_do_not_move_between_refreshes(app):
    """A demonstration that changes its figures on a reload is not a
    demonstration. Same seed, same story."""
    from app.demo import demo_analysis
    with app.app_context():
        a_rows, a_totals, a_stages = demo_analysis()
        b_rows, b_totals, b_stages = demo_analysis()
    assert a_totals == b_totals
    assert [r["done"] for r in a_rows] == [r["done"] for r in b_rows]
    assert [s["submitted"] for s in a_stages] == [s["submitted"] for s in b_stages]
    assert all(r["demo"] for r in a_rows)
    assert a_totals["departments"] == len(a_rows)


def test_every_stage_row_adds_up_to_the_department_count(app):
    """A table whose rows do not sum invites doubt about all of it."""
    from app.demo import demo_analysis
    with app.app_context():
        rows, totals, stages = demo_analysis()
    for s in stages:
        counted = s["submitted"] + s["draft"] + s["returned"] + s["open"] + s["locked"]
        assert counted == totals["departments"], (s["title"], counted)


# ---------------------------------------------------------- developer mode

def set_dev_mode(app, on):
    from app.db import get_db
    with app.app_context():
        get_db().settings.update_one({"_id": "app"}, {"$set": {"dev_mode": on}},
                                     upsert=True)


def test_developer_mode_opens_a_stage_the_lock_would_have_held(app, client):
    """The point of the switch: reach stage thirteen without filing twelve."""
    u, p = make_department(app)
    login(client, u, p)

    # the lock holds, as it does for a department in the ordinary way
    r = client.get("/department/stage/pre_bos", follow_redirects=True)
    assert "opens once you have submitted" in r.get_data(as_text=True)

    set_dev_mode(app, True)
    assert client.get("/department/stage/pre_bos").status_code == 200
    # not merely the next one along — the last stage of all opens too
    from app.schema import STAGE_KEYS
    assert client.get("/department/stage/" + STAGE_KEYS[-1]).status_code == 200

    # and turning it off puts the lock back
    set_dev_mode(app, False)
    r = client.get("/department/stage/pre_bos", follow_redirects=True)
    assert "opens once you have submitted" in r.get_data(as_text=True)


def test_developer_mode_does_not_rewrite_what_is_already_filed(app):
    """It is a view of the data, not a change to it.

    A stage that was submitted stays submitted, and one that was sent back
    stays sent back — the switch only ever turns `locked` into `open`.
    """
    from app.workflow import compute_status, get_or_create_submission, stage_board
    from app.db import get_db
    from app.schema import STAGE_KEYS

    with app.app_context():
        sub = get_or_create_submission("COM", "2027-28")
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": {
            "stages." + STAGE_KEYS[0]: {"status": "submitted"},
            "stages." + STAGE_KEYS[1]: {"status": "returned"},
        }})
        sub = get_db().submissions.find_one({"_id": sub["_id"]})

        off = {s["key"]: s["status"] for s in stage_board(sub, dev=False)}
        on = {s["key"]: s["status"] for s in stage_board(sub, dev=True)}

        assert off[STAGE_KEYS[0]] == on[STAGE_KEYS[0]] == "submitted"
        assert off[STAGE_KEYS[1]] == on[STAGE_KEYS[1]] == "returned"
        # every difference between the two is a lock that was lifted
        for key in off:
            if off[key] != on[key]:
                assert (off[key], on[key]) == ("locked", "open"), key
        assert "locked" not in on.values()
        assert compute_status(sub, STAGE_KEYS[-1], dev=True) == "open"


def test_developer_mode_says_so_on_every_page(app, client):
    """It is easy to switch on and easy to forget, so it announces itself."""
    u, p = make_department(app)
    login(client, u, p)
    assert "Developer Preview" not in client.get("/department/").get_data(as_text=True)

    set_dev_mode(app, True)
    for path in ("/department/", "/department/stage/dept_info"):
        assert "Developer Preview" in client.get(path).get_data(as_text=True), path


def test_the_switch_is_on_the_settings_page_and_is_logged(app, client):
    """Unlocking every department at once leaves a trace in the audit log."""
    from app.db import get_db
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    assert 'name="dev_mode"' in client.get("/admin/settings").get_data(as_text=True)

    client.post("/admin/settings", data={"academic_year": "2027-28",
                                         "dev_mode": "on", "banner": ""})
    with app.app_context():
        assert get_db().settings.find_one({"_id": "app"})["dev_mode"] is True
        assert get_db().audit.find_one({"action": "settings.dev_mode.on"})

    # saving the form again without the box ticked turns it off
    client.post("/admin/settings", data={"academic_year": "2027-28", "banner": ""})
    with app.app_context():
        assert get_db().settings.find_one({"_id": "app"})["dev_mode"] is False
        assert get_db().audit.find_one({"action": "settings.dev_mode.off"})


def test_a_department_still_cannot_reach_the_switch(app, client):
    """Developer mode unlocks stages, not the admin console."""
    u, p = make_department(app)
    login(client, u, p)
    set_dev_mode(app, True)
    assert client.get("/admin/settings").status_code == 403
    assert client.post("/admin/settings", data={"dev_mode": "on"}).status_code == 403


# --------------------------------------------------------------------------
# Department Information: identity cards and the programme list

def test_department_information_lists_the_workbook_programmes(app, client):
    u, p = make_department(app, code="COMM-JYN")
    with app.app_context():
        from app.db import get_db
        get_db().departments.update_one({"dept_code": "COMM-JYN"},
                                        {"$set": {"campus": "Jayanagar Campus"}})
    login(client, u, p)
    body = client.get("/department/stage/dept_info").get_data(as_text=True)
    data = json.loads(body.split('id="stage-data" type="application/json">')[1]
                      .split("</script>")[0])
    codes = [r["programme_code"] for r in data["programmes_offered"]]
    assert "BCMREG" in codes and "BCHCOF" in codes
    assert all(r["decision"] == "keep" for r in data["programmes_offered"])
    assert "magic-bento.js" in body


def test_programme_list_must_keep_one_and_new_rows_need_details(app, client):
    u, p = make_department(app)
    login(client, u, p)
    bad = dict(DEPT_INFO_OK, programmes_offered=[
        {"programme_code": "BCMREG", "programme_name": "B.Com", "source": "catalogue",
         "decision": "remove"},
        {"programme_code": "", "programme_name": "", "source": "new", "decision": "keep"},
    ])
    body = client.post("/department/api/dept_info/submit", json=bad).get_json()
    assert body["ok"] is False
    msgs = " ".join(i["message"] for i in body["issues"])
    assert "needs a name" in msgs and "needs a code" in msgs and "UG, PG" in msgs


def test_a_removed_programme_needs_a_reason(app, client):
    u, p = make_department(app)
    login(client, u, p)
    rows = [dict(r) for r in PROGRAMMES_OK]
    rows[1].pop("removal_reason")
    body = client.post("/department/api/dept_info/submit",
                       json=dict(DEPT_INFO_OK, programmes_offered=rows)).get_json()
    assert body["ok"] is False
    assert any("being removed" in i["message"] for i in body["issues"])

    rows[1]["removal_reason"] = "Other"
    body = client.post("/department/api/dept_info/submit",
                       json=dict(DEPT_INFO_OK, programmes_offered=rows)).get_json()
    assert any("add a line" in i["message"] for i in body["issues"])

    rows[1]["removal_note"] = "Folded into BCMREG"
    assert client.post("/department/api/dept_info/submit",
                       json=dict(DEPT_INFO_OK, programmes_offered=rows)).get_json()["ok"]




def test_flow_mapping_shows_each_department_at_its_stage(app, client):
    _through_bos_documents(app, client)
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    page = client.get("/admin/flow").get_data(as_text=True)
    assert "Department to stage mapping" in page and "/admin/flow.xlsx" in page

    data = client.get("/admin/flow.json").get_json()
    com = next(d for d in data["departments"] if d["code"] == "COM")
    assert com["reached"] == 3                       # at Curriculum
    assert com["statuses"]["bos_documents"] == "submitted"
    assert {p["level"] for p in com["programmes"]} == {"UG", "PG"}

    x = client.get("/admin/flow.xlsx")
    assert x.status_code == 200 and x.data[:2] == b"PK"
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(x.data))
    assert wb.sheetnames == ["Department to stage", "Programmes"]
    rows = list(wb["Department to stage"].iter_rows(min_row=4, values_only=True))
    assert any(r[1] == "COM" and r[4] == "Curriculum" for r in rows)
