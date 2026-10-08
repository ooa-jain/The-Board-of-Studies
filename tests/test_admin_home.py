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
