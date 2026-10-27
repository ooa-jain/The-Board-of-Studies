"""Once every part of a programme is submitted, the department reads its
report — the one the Office reads — under each of its pages, and finds every
programme's report on its home page, to view or download."""

from test_workflow import login


def _demo(app, client):
    from app import demo_dept
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    return "DEMOBBA"


def test_a_submitted_programme_shows_its_report(app, client):
    code = _demo(app, client)
    page = client.get(f"/department/stage/prog_syllabus/{code}").get_data(as_text=True)
    assert 'id="programme-report"' not in page                 # not every part is in yet
    assert 'id="btn-save-draft"' not in page                   # changes save by themselves
    # Submit sits at the end of the form, not fixed on the screen
    assert 'class="savebar savebar-end"' in page and page.index('id="stage-form"') < page.index('id="btn-submit"')

    # the home page: every programme, to view or download
    home = client.get("/department/").get_data(as_text=True)
    assert "Submissions" in home
    assert f'href="/department/programme/{code}/report"' in home
    assert f'href="/department/programme/{code}/report.zip" download' in home

    # submit every part of the programme
    items = client.get(f"/department/api/record?programme={code}").get_json()["items"]
    for it in items:
        j = client.post(f"/department/api/{it['key']}/{code}/submit", json=it["data"]).get_json()
        assert j["ok"], (it["key"], j)

    page = client.get(f"/department/stage/prog_syllabus/{code}").get_data(as_text=True)
    report = page[page.index('id="programme-report"'):]
    assert "Programme report" in report and "✓ Submitted" in report
    assert "Programme structure" in report and "Course Revision" in report
    assert f'href="/department/programme/{code}/report.zip" download' in report
    # the same under the Curriculum's page
    assert 'id="programme-report"' in client.get(f"/department/stage/prog_curriculum/{code}").get_data(as_text=True)
    assert "✓ Submitted" in client.get("/department/").get_data(as_text=True)

    # its report as a page of its own, as the Office has it
    r = client.get(f"/department/programme/{code}/report")
    text = r.get_data(as_text=True)
    assert r.status_code == 200 and "Download all (ZIP)" in text and "/admin/" not in text
    assert client.get("/department/programme/NOPE/report").status_code == 404
