"""Overview › Faculties: faculty → school → department, and each level as a
ZIP of every department's Excel and Word, folder by folder."""

import io
import zipfile

from test_workflow import DEPT_INFO_OK, login, make_department


def _three(app):
    make_department(app)                                                        # COM
    make_department(app, code="ENG", name="Department of English", school="School of Humanities")
    make_department(app, code="LAW", name="Department of Law", school="School of Law")
    from app.db import get_db
    with app.app_context():
        db = get_db()
        db.departments.update_many({"dept_code": {"$in": ["COM", "ENG"]}}, {"$set": {"faculty": "Faculty of Arts"}})
        db.departments.update_one({"dept_code": "LAW"}, {"$set": {"faculty": "Faculty of Law"}})


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_faculties_then_schools_then_departments(app, client):
    _three(app)
    u, p = "com", "DeptPassword1!"
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    client.get("/logout")
    _admin(app, client)
    # Overview's tabs are Departments first; Monitor, Faculties and Analysis are no longer tabs
    head = client.get("/admin/overview/departments").get_data(as_text=True)
    assert ">Departments</a>" in head and ">Monitor</a>" not in head and ">Faculties</a>" not in head

    page = client.get("/admin/faculties").get_data(as_text=True)
    assert "Faculty of Arts" in page and "Faculty of Law" in page and "2 faculties" in page
    assert "/admin/export/group.zip?faculty=Faculty+of+Arts" in page

    page = client.get("/admin/faculties?faculty=Faculty+of+Arts").get_data(as_text=True)
    assert "School of Commerce" in page and "School of Humanities" in page and "School of Law" not in page
    assert "Download the faculty (ZIP)" in page

    page = client.get("/admin/faculties?faculty=Faculty+of+Arts&school=School+of+Commerce").get_data(as_text=True)
    assert "Department of Commerce" in page and "Department of English" not in page
    assert "/admin/export/COM.xlsx" in page and "/admin/export/COM.docx" in page
    assert "Download the school (ZIP)" in page and "1/4" in page

    # a faculty or school that is not there goes back to the list
    assert client.get("/admin/faculties?faculty=Nowhere").status_code == 302


def test_a_faculty_downloads_as_folders_of_schools_with_each_department_s_excel_and_word(app, client):
    _three(app)
    _admin(app, client)
    r = client.get("/admin/export/group.zip?faculty=Faculty+of+Arts")
    assert r.status_code == 200 and r.mimetype == "application/zip"
    assert "BoS-Faculty-of-Arts-" in r.headers["Content-Disposition"]
    names = set(zipfile.ZipFile(io.BytesIO(r.data)).namelist())
    assert names == {
        "Faculty of Arts/Faculty of Arts - summary.xlsx",
        "Faculty of Arts/School of Commerce/School of Commerce - summary.xlsx",
        "Faculty of Arts/School of Commerce/COM - Department of Commerce.xlsx",
        "Faculty of Arts/School of Commerce/COM - Department of Commerce.docx",
        "Faculty of Arts/School of Humanities/School of Humanities - summary.xlsx",
        "Faculty of Arts/School of Humanities/ENG - Department of English.xlsx",
        "Faculty of Arts/School of Humanities/ENG - Department of English.docx",
    }
    # a school: its departments, in one folder
    r = client.get("/admin/export/group.zip?faculty=Faculty+of+Law&school=School+of+Law")
    names = set(zipfile.ZipFile(io.BytesIO(r.data)).namelist())
    assert names == {"School of Law/School of Law - summary.xlsx", "School of Law/LAW - Department of Law.xlsx",
                     "School of Law/LAW - Department of Law.docx"}
    # the files open
    from openpyxl import load_workbook
    z = zipfile.ZipFile(io.BytesIO(r.data))
    wb = load_workbook(io.BytesIO(z.read("School of Law/School of Law - summary.xlsx")))
    assert "School of Law status" in wb.active["A1"].value
    assert client.get("/admin/export/group.zip?faculty=Nowhere").status_code == 404


def test_departments_without_a_faculty_are_still_listed(app, client):
    make_department(app)
    _admin(app, client)
    assert "Faculty not set" in client.get("/admin/faculties").get_data(as_text=True)


def test_the_place_in_the_top_bar_changes_every_page(app, client):
    _three(app)
    from app.db import get_db
    with app.app_context():
        get_db().departments.update_many({}, {"$set": {"place": "Bangalore"}})
        get_db().departments.update_one({"dept_code": "LAW"}, {"$set": {"place": "Kochi"}})
    _admin(app, client)
    home = client.get("/admin/").get_data(as_text=True)
    assert 'class="erp-place"' in home and "Department of Law" in home and "Department of Commerce" in home
    r = client.get("/admin/place?to=Kochi&next=/admin/")
    assert r.status_code == 302 and r.location.endswith("/admin/")
    home = client.get("/admin/").get_data(as_text=True)
    assert "Department of Law" in home and "Department of Commerce" not in home
    assert 'aria-current="true">Kochi</a>' in home
    assert "Department of Commerce" not in client.get("/admin/submissions").get_data(as_text=True)
    page = client.get("/admin/faculties").get_data(as_text=True)
    assert "Faculty of Law" in page and "Faculty of Arts" not in page
    # a department elsewhere still opens; the place is a view, not a permission
    assert client.get("/admin/submissions/COM").status_code == 200
    # the department master starts at the place, and its own chips can show all
    assert "Department of Commerce" not in client.get("/admin/departments").get_data(as_text=True)
    assert "Department of Commerce" in client.get("/admin/departments?place=").get_data(as_text=True)
    # back to all; an unknown place is all
    client.get("/admin/place?to=Mars")
    assert "Department of Commerce" in client.get("/admin/").get_data(as_text=True)
    # nowhere outside the portal to be sent
    assert client.get("/admin/place?to=Kochi&next=//evil.example").location.endswith("/admin/")


def test_a_zip_holds_excel_word_or_both_as_asked(app, client):
    _three(app)
    _admin(app, client)
    page = client.get("/admin/faculties").get_data(as_text=True)
    assert 'id="fx-ask"' in page and "Excel only" in page and "Word only" in page
    r = client.get("/admin/export/group.zip?faculty=Faculty+of+Law&school=School+of+Law&kind=xlsx")
    assert "-Excel-" in r.headers["Content-Disposition"]
    names = set(zipfile.ZipFile(io.BytesIO(r.data)).namelist())
    assert names == {"School of Law/School of Law - summary.xlsx", "School of Law/LAW - Department of Law.xlsx"}
    r = client.get("/admin/export/group.zip?faculty=Faculty+of+Law&school=School+of+Law&kind=docx")
    assert "-Word-" in r.headers["Content-Disposition"]
    assert set(zipfile.ZipFile(io.BytesIO(r.data)).namelist()) == {"School of Law/LAW - Department of Law.docx"}
