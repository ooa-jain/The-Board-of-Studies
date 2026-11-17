"""A department sees what it has submitted — each Curriculum, Syllabus and
Course Revision, every batch, as the Office's Word templates lay them out —
under Reports and from its submitted pages. It sees; it does not download:
a copy comes from the Office of Academic Affairs."""

from test_workflow import login


def _demo(app, client):
    from app import demo_dept
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    return "DEMOBBA"


def test_a_department_sees_its_submission_without_a_download(app, client):
    code = _demo(app, client)
    page = client.get(f"/department/stage/prog_syllabus/{code}").get_data(as_text=True)
    assert 'id="programme-done"' not in page                   # not every part is in yet
    assert 'id="btn-save-draft"' not in page                   # changes save by themselves
    # Submit sits at the end of the form, not fixed on the screen
    assert 'class="savebar savebar-end"' in page and page.index('id="stage-form"') < page.index('id="btn-submit"')

    # nothing submitted yet: Reports says so
    home = client.get("/department/").get_data(as_text=True)
    assert "Submissions" in home and "report.zip" not in home and "Nothing submitted yet" in home
    assert 'href="/department/reports"' in home                  # Reports, in the side menu
    seen = client.get(f"/department/programme/{code}/report").get_data(as_text=True)
    assert "Nothing of DEMOBBA is submitted yet" in seen

    # submit every part of the programme
    items = client.get(f"/department/api/record?programme={code}").get_json()["items"]
    for it in items:
        j = client.post(f"/department/api/{it['key']}/{code}/submit", json=it["data"]).get_json()
        assert j["ok"], (it["key"], j)

    page = client.get(f"/department/stage/prog_syllabus/{code}").get_data(as_text=True)
    done = page[page.index('id="programme-done"'):]
    assert "See your submission" in done and f'href="/department/programme/{code}/report"' in done
    assert "report.zip" not in page and "Download a copy" not in page and "Download all" not in page
    # beside Review: this page's own document
    assert f'href="/department/programme/{code}/report?batch=current&amp;doc=s"' in page

    # Reports: every programme, to see
    reports = client.get("/department/reports").get_data(as_text=True)
    assert "See your submission" in reports and f"/department/programme/{code}/report" in reports

    # the document as its Word template lays it out — the syllabus sheet's headings and tables
    seen = client.get(f"/department/programme/{code}/report?batch=current&doc=s").get_data(as_text=True)
    assert 'class="gen-doc' in seen and "Course Information:" in seen and "CO-PO-PSO Mapping:" in seen
    assert 'aria-current="page"' in seen and "View only" in seen and "Office of Academic Affairs" in seen
    # nothing to download or print from: no download link, no Word file, no share link, no Print button
    html = seen.split("<script")[0]                              # the page, not its scripts
    assert "Download" not in html and " download" not in html and "/share/" not in html
    assert ".docx" not in html and 'type="button" data-print' not in html
    # every batch's three documents are there to pick
    for batch in ("current", "prog_syllabus_b2024", "prog_syllabus_b2025"):
        for doc in ("c", "s", "v"):
            assert f"batch={batch}&amp;doc={doc}" in seen, (batch, doc)
    seen = client.get(f"/department/programme/{code}/report?batch=current&doc=v").get_data(as_text=True)
    assert "Percentage of change in syllabus revision" in seen
    seen = client.get(f"/department/programme/{code}/report?batch=current&doc=c").get_data(as_text=True)
    assert "Programme Outcomes (POs)" in seen

    # another department's programme, or none, is not shown
    assert client.get("/department/programme/NOPE/report").status_code == 404
    # and there is no download for the department, of any report
    for url in (f"/department/programme/{code}/report.zip", "/department/export.xlsx", "/department/export.docx"):
        assert client.get(url).status_code == 404, url
