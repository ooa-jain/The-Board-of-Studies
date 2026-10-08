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
    # the overview tabs offer it too
    assert "Analysis in one click" in client.get("/admin/submissions").get_data(as_text=True)


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
    """PG: Generic Core … Research / Thesis / Project / Patent, no Honours
    tracks or minors, a Fee item, 60 / 40; UG unchanged."""
    from app.schema import PG_CATEGORIES, STAGE_BY_KEY, for_level, pg_category, pg_groups
    base = STAGE_BY_KEY["prog_curriculum"]
    assert for_level(base, "UG - 4 Year (Honours with Research)") is base
    pg = for_level(base, "PG - 2 Year")
    keys = [s["key"] for s in pg["sections"]]
    assert "minors" not in keys and pg["level"] == "PG"
    struct = next(s for s in pg["sections"] if s["key"] == "semester_structure")
    cols = {c["name"]: c for c in struct["columns"]}
    assert "track" not in cols and cols["nep_category"]["options"] == PG_CATEGORIES
    prof = next(s for s in pg["sections"] if s["key"] == "profile")
    assert "fee" in [f["name"] for f in prof["fields"]]
    assert "60% Continuous Assessment" in next(f for f in prof["fields"] if f["name"] == "assessment")["prefill_text"]
    # a UG group saved for a PG programme reads as its PG classification
    assert pg_category("Major (Core)") == "Generic Core"
    assert pg_category("Discipline Specific Elective (DSE)") == "Generic Elective"
    assert pg_category("Research Project / Dissertation") == "Research / Thesis / Project / Patent"
    assert pg_category("Major (Core)", 4, "Project Management") == "Generic Core"
    data = pg_groups({"semester_structure": [{"nep_category": "Multidisciplinary", "track": "All semesters"}]}, "PG - 2 Year")
    assert data["semester_structure"][0] == {"nep_category": "Open Elective"}
