"""The Office's home, white and at a glance, and its analysis in one click."""

from test_workflow import DEPT_INFO_OK, login, make_department


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_the_home_reads_the_institution_at_a_glance(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    page = client.get("/admin/").get_data(as_text=True)
    for words in ("Stages completed", "Programmes completed", "Needs attention", "Progress by stage",
                  "furthest behind first", "By campus", "Latest from departments"):
        assert words in page, words
    # the old navy Overview panel is gone; the analysis is one click away
    assert "dash-overview" not in page
    assert 'href="/admin/analysis/report"' in page
    # Department Information is completed by one department of one
    assert 'data-tip="1|Completed · Department Information|100% of 1 departments"' in page


def test_the_analysis_says_what_the_numbers_mean(app, client):
    make_department(app)
    make_department(app, code="ENG", name="Department of English")
    _admin(app, client)
    page = client.get("/admin/analysis/report").get_data(as_text=True)
    assert "Key findings" in page and "Print / Save as PDF" in page
    assert "0% of all stages are completed" in page
    assert "2 departments have filed nothing yet" in page
    for words in ("Stage by stage", "Programmes", "By campus", "By school", "Departments, ranked"):
        assert words in page, words
    # one way in: from Home, not repeated on every Overview tab
    assert "Analysis in one click" not in client.get("/admin/submissions").get_data(as_text=True)


def test_the_sign_in_page_is_light_with_the_scene_as_its_picture(app, client):
    page = client.get("/").get_data(as_text=True)
    assert "img/jain-logo.png" in page and "jain-logo-light.png" not in page
    assert "login-stage-cap" in page and "Every stage, ticked off" in page


def test_a_department_s_changes_carry_a_red_tag_until_the_office_marks_them_seen(app, client):
    u, p = make_department(app)
    dept = client
    login(dept, u, p)
    dept.post("/department/api/dept_info/save", json=DEPT_INFO_OK)
    dept.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    office = app.test_client()
    _admin(app, office)
    grid = office.get("/admin/submissions").get_data(as_text=True)
    assert 'class="upd-tag"' in grid and "dot st-submitted is-upd" in grid
    assert 'class="upd-tag"' in office.get("/admin/").get_data(as_text=True)
    page = office.get("/admin/submissions/COM").get_data(as_text=True)
    assert "since you last looked" in page and "Mark as seen" in page
    # seen: the tags go
    office.post("/admin/submissions/COM/seen")
    page = office.get("/admin/submissions/COM").get_data(as_text=True)
    assert "upd-banner" not in page
    assert 'class="upd-tag"' not in office.get("/admin/submissions").get_data(as_text=True)


def test_titles_are_offered_while_typing(app, client):
    """The stage page carries the titles to suggest — the university's
    programmes, the department's courses — and the widget is loaded."""
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/stage/dept_info").get_data(as_text=True)
    assert "js/suggest.js" in page and "window.SUGGEST_PHRASES" in page
    assert "Bachelor of Commerce (Honours / Honours with Research)" in page


def test_short_forms_expand_to_full_words():
    """CS is Computer Science or Cyber Security; comm is Commerce or Communication."""
    import re
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "suggest.js").read_text()
    assert re.search(r'cs: \["Computer Science", "Cyber Security"', js)
    assert re.search(r'comm: \["Commerce", "Communication"', js)


def test_a_pg_curriculum_is_the_pg_course_matrix_and_ug_stays_as_it_was():
    """PG: the same course categories as UG, no Honours tracks or minors, a
    Fee item, 60 / 40; UG unchanged."""
    from app.schema import NEP_CATEGORIES, STAGE_BY_KEY, course_category, for_level, category_groups
    base = STAGE_BY_KEY["prog_curriculum"]
    assert for_level(base, "UG - 4 Year (Honours with Research)") is base
    pg = for_level(base, "PG - 2 Year")
    keys = [s["key"] for s in pg["sections"]]
    assert "minors" not in keys and pg["level"] == "PG"
    struct = next(s for s in pg["sections"] if s["key"] == "semester_structure")
    cols = {c["name"]: c for c in struct["columns"]}
    assert "track" not in cols and cols["nep_category"]["options"] == NEP_CATEGORIES
    prof = next(s for s in pg["sections"] if s["key"] == "profile")
    assert "fee" in [f["name"] for f in prof["fields"]]
    assert "60% Continuous Assessment" in next(f for f in prof["fields"] if f["name"] == "assessment")["prefill_text"]
    # a category stays as it is; an older draft's words read as the category they stand for
    assert course_category("Major (Core)") == "Major (Core)"
    assert course_category("Discipline Specific Elective (DSE)") == "Major (Core)"
    assert course_category("Mandatory Non-Credit Audit Course") == "Major (Core)"
    assert course_category("Generic Core") == "Major (Core)"
    assert course_category("Specialisation Elective") == "Major (Core)"
    assert course_category("Open Elective") == "Multidisciplinary"
    assert course_category("Research / Thesis / Project / Patent") == "Research Project / Dissertation"
    assert course_category("Major (Core)", 4, "Project Management") == "Major (Core)"
    assert course_category("", 4, "Summer Internship in industry") == "Summer Internship"
    assert course_category("Anything else", 0) == "Major (Core)"
    data = category_groups({"semester_structure": [{"nep_category": "Generic Core", "track": "All semesters"}]}, "PG - 2 Year")
    assert data["semester_structure"][0] == {"nep_category": "Major (Core)"}
    # an earlier batch's PG list offers the same categories
    batch = for_level(STAGE_BY_KEY["prog_syllabus_b2025"], "PG - 2 Year")
    bcols = {c["name"]: c for c in next(s for s in batch["sections"] if s["key"] == "batch_courses")["columns"]}
    assert bcols["nep_category"]["options"] == NEP_CATEGORIES
    # the list is the credit table's own eight headings, and nothing else
    from app.schema import CATEGORY_LABELS
    assert [CATEGORY_LABELS[c] for c in NEP_CATEGORIES] == [
        "Major", "Minor", "Multi-Disciplinary / OE", "Ability Enhancement / AEC", "Skill Enhancement / SEC",
        "Common Value Added / VAC", "Summer Internship / INTERNSHIP", "Research Project / Dissertation / PROJECT"]
    assert cols["nep_category"]["option_labels"] == CATEGORY_LABELS
    # a UG programme's saved Discipline Specific Elective reads as Major, and keeps its track
    ug = category_groups({"semester_structure": [{"nep_category": "Discipline Specific Elective (DSE)",
                                                  "track": "Honours"}]}, "UG - 4 Year (Honours)")
    assert ug["semester_structure"][0] == {"nep_category": "Major (Core)", "track": "Honours"}


def test_the_home_is_live_and_every_number_says_where_it_comes_from(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    page = client.get("/admin/").get_data(as_text=True)
    assert 'id="ad-live"' in page and "js/admin-live.js" in page and "data-src-toggle" in page
    assert page.count('class="ad-src"') >= 8
    assert "How it is counted" in page and "as of" in page
    # the departments behind a number, by name
    assert "Most completed first" in page and "Department of Commerce" in page
    assert 'href="/admin/motion"' in page


def test_motion_plays_the_year_from_the_same_numbers(app, client):
    import json, re
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    page = client.get("/admin/motion").get_data(as_text=True)
    assert "js/motion.js" in page and 'id="mo-canvas"' in page and "Download video" in page
    data = json.loads(re.search(r"window.MOTION_DATA = (\{.*?\});</script>", page, re.S).group(1))
    assert data["totals"]["departments"] == 1 and data["totals"]["stages_done"] == 1
    assert data["year"] == "2027–28" and data["scope"] == "All departments"
    assert data["stages"][0]["done"] == 1 and data["findings"]
    # the same words, as text, for anyone who cannot watch it
    assert "Everything the animation says, as text" in page


def test_each_thing_has_one_place_in_the_menu(app, client):
    """Documents and Comments are Overview tabs, Calendar opens from Updates,
    and the Excel download lives on Overview only."""
    _admin(app, client)
    home = client.get("/admin/").get_data(as_text=True)
    side = home.split('class="side-nav"')[1].split("</nav>")[0]
    for gone in ('title="Documents"', 'title="Comments"', 'title="Calendar"'):
        assert gone not in side, gone
    assert 'title="Overview"' in side and 'title="Change Password"' in side
    assert "/admin/sheets.xlsx" not in home
    overview = client.get("/admin/submissions").get_data(as_text=True)
    assert "/admin/sheets.xlsx" in overview and ">Documents<" in overview and ">Comments<" in overview
    assert "/admin/calendar" in client.get("/admin/updates").get_data(as_text=True)
    assert client.get("/admin/calendar").status_code == 200


def test_overview_departments_lists_each_and_more_opens_its_page(app, client):
    """Overview opens on Departments: each with its progress and downloads;
    More opens the department's page — when it last moved, its stages, its
    programmes by level, and the versions beside."""
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    page = client.get("/admin/overview/departments").get_data(as_text=True)
    assert "Department of Commerce" in page and "1/4 stages" not in page
    assert 'href="/admin/overview/departments/COM"' in page and "/admin/export/COM.xlsx" in page
    more = client.get("/admin/overview/departments/COM").get_data(as_text=True)
    assert "last edited" in more and "Stages" in more and "Versions" in more
    assert "Download report" in more and "/admin/export/COM.zip" in more
    assert client.get("/admin/overview/departments/NOPE").status_code == 404


def test_department_page_downloads_both_and_deletes_with_the_code_typed(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/save", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    r = client.get("/admin/export/COM.zip")
    assert r.status_code == 200 and r.mimetype == "application/zip"
    # the data goes, the department stays — and only with the code typed
    client.post("/admin/departments/COM/wipe", data={"confirm": "nope", "back": "page"})
    with app.app_context():
        assert get_db().submissions.count_documents({"dept_code": "COM"}) == 1
    r = client.post("/admin/departments/COM/wipe", data={"confirm": "COM", "back": "page"})
    assert r.location.endswith("/admin/overview/departments/COM")
    with app.app_context():
        assert get_db().submissions.count_documents({"dept_code": "COM"}) == 0
        assert get_db().departments.count_documents({"dept_code": "COM"}) == 1
    r = client.post("/admin/departments/COM/delete", data={"confirm": "COM", "back": "page"})
    assert r.location.endswith("/admin/overview/departments")
    with app.app_context():
        assert get_db().departments.count_documents({"dept_code": "COM"}) == 0
        assert get_db().users.count_documents({"dept_code": "COM", "role": "department"}) == 0


def test_next_batch_moves_the_current_syllabus_to_an_earlier_batch(app, client):
    from app.db import get_db
    from app.workflow import batches
    make_department(app)
    with app.app_context():
        db = get_db()
        db.settings.update_one({"_id": "app"}, {"$set": {"current_batch": "2026-2027",
                                                         "existing_batches": ["2024-2025", "2025-2026"]}}, upsert=True)
        db.submissions.update_one({"dept_code": "COM"}, {"$set": {
            "programmes.BCOM.prog_syllabus": {"status": "submitted", "data": {"courses": [{"course_code": "C1"}]}},
            "programmes.BCOM.prog_curriculum": {"status": "draft", "data": {"x": 1}}}}, upsert=True)
    _admin(app, client)
    page = client.get("/admin/settings").get_data(as_text=True)
    assert "Make 2027–2028 the current batch" in page
    r = client.post("/admin/settings/next-batch", data={"from": "2026–2027"})
    assert r.status_code == 302
    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        p = sub["programmes"]["BCOM"]
        assert "prog_syllabus" not in p and p["prog_syllabus_b2026"]["status"] == "submitted"
        assert p["prog_curriculum"]["data"] == {"x": 1}
        b = batches()
        assert b["current"] == "2027–2028"
        assert [x["label"] for x in b["existing"]] == ["2024–2025", "2025–2026", "2026–2027"]
    # the same click again (an old page) changes nothing
    client.post("/admin/settings/next-batch", data={"from": "2026–2027"})
    with app.app_context():
        from app.workflow import batches as again
        assert again()["current"] == "2027–2028"


def test_settings_choose_the_semesters_each_earlier_batch_uploads(app, client):
    from app.db import get_db
    from app.dept import _batch_semesters
    from app.schema import STAGE_BY_KEY
    from app.workflow import batches
    with app.app_context():
        get_db().settings.update_one({"_id": "app"}, {"$set": {"current_batch": "2026-2027",
                                                               "existing_batches": ["2024-2025", "2025-2026"]}},
                                     upsert=True)
    _admin(app, client)
    page = client.get("/admin/settings").get_data(as_text=True)
    assert "Semesters each earlier batch covers" in page and 'name="sems_2024"' in page
    r = client.post("/admin/settings", data={
        "academic_year": "2026-27", "current_batch": "2026-2027", "existing_batches": "2024-2025\n2025-2026",
        "sems_2024_shown": "1", "sems_2024": ["5", "6"], "sems_2025_shown": "1", "sems_2025": ["3", "4"]})
    assert r.status_code == 302
    with app.app_context():
        b = {x["label"]: x["semesters"] for x in batches()["existing"]}
        assert b == {"2024–2025": [5, 6], "2025–2026": [3, 4]}
        sec = _batch_semesters(STAGE_BY_KEY["prog_syllabus_b2024"])["sections"][0]
        assert "studied in semesters 5 and 6" in sec["help"] and sec["title"].endswith("Semesters 5 and 6")
        sem = next(c for c in sec["columns"] if c["name"] == "semester")
        assert sem["choices"] == [5, 6]
    page = client.get("/admin/settings").get_data(as_text=True)
    import re
    assert re.search(r'name="sems_2024" value="5"\s+checked', page)
    assert not re.search(r'name="sems_2024" value="4"\s+checked', page)
