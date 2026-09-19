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
    assert "UGC Table 2" in body
    assert "Board of Studies" in body


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
                 "dept_code": "COM", "campus": "Jain Global Campus"},
    "contact": {"office_email": "office@example.edu", "faculty_count": 24,
                "programme_count": 3},
}


PRE_BOS_FILES_OK = {
    "pre_bos_files": {
        "diac_signed": {"name": "diac.pdf", "stored": "a.pdf", "size": 1024},
        "bos_signed": {"name": "bos.pdf", "stored": "b.pdf", "size": 1024},
        "pac_signed": {"name": "pac.pdf", "stored": "c.pdf", "size": 1024},
    },
}


def test_pre_bos_requires_all_three_signed_documents(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit",
                       json=DEPT_INFO_OK).get_json()["ok"]

    # nothing uploaded — all three are named as missing
    r = client.post("/department/api/pre_bos/validate", json={})
    msgs = [i["message"] for i in r.get_json()["issues"]]
    assert any("Department Industry-Academia Cell" in m for m in msgs)
    assert any("Board of Studies" in m for m in msgs)
    assert any("Programme Assessment Committee" in m for m in msgs)

    # one still missing — the submit is refused
    partial = {"pre_bos_files": dict(PRE_BOS_FILES_OK["pre_bos_files"])}
    partial["pre_bos_files"].pop("pac_signed")
    assert not client.post("/department/api/pre_bos/submit", json=partial).get_json()["ok"]

    # all three present — it goes through
    assert client.post("/department/api/pre_bos/submit",
                       json=PRE_BOS_FILES_OK).get_json()["ok"]


def test_pre_bos_no_longer_collects_composition_tables(app, client):
    """The three tables were replaced by uploads; their rules are gone with them."""
    from app.schema import STAGE_BY_KEY
    keys = {s["key"] for s in STAGE_BY_KEY["pre_bos"]["sections"]}
    assert keys == {"pre_bos_files", "pre_bos_extra"}
    assert not any(s.get("type") == "table"
                   for s in STAGE_BY_KEY["pre_bos"]["sections"])


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
    assert "Your next step" in body
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
            "stages.bos_committee.status": "returned",
        }})
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        nxt = next_action(sub)
        assert nxt["key"] == "bos_committee"
        assert nxt["status"] == "returned"


def test_next_action_is_none_once_everything_is_submitted(app):
    from app.workflow import next_action, get_or_create_submission
    from app.db import get_db
    from app.schema import STAGE_KEYS
    make_department(app)
    with app.app_context():
        sub = get_or_create_submission("COM", app.config["ACADEMIC_YEAR"])
        get_db().submissions.update_one({"_id": sub["_id"]}, {"$set": {
            f"stages.{k}.status": "submitted" for k in STAGE_KEYS}})
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
                     "campus": "Jain Global Campus"},
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
        assert [g["name"] for g in groups][0] == "Department"
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
    assert "OOA Data Portal" in body or "Office of Academics Data Portal" in body
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
    assert "0 of 13 stages submitted" in body
    assert "Your next step" in body and "Department Information" in body

    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    body = client.get("/").get_data(as_text=True)
    assert "1 of 13 stages submitted" in body
    assert "Pre-BoS" in body


def test_the_admin_gets_the_console_not_a_department_panel(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    body = client.get("/").get_data(as_text=True)
    assert 'name="password"' not in body
    assert "The admin dashboard" in body
    assert "stages submitted" not in body
