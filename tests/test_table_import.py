"""Filling the programme structure from the department's Excel or CSV."""

import io
from pathlib import Path

import pytest

from app.schema import STAGE_BY_KEY
from app.table_import import ImportError_, rows_from_file

SECTION = next(s for s in STAGE_BY_KEY["prog_curriculum"]["sections"] if s["key"] == "semester_structure")


def _xlsx(tmp_path, rows, name="matrix.xlsx"):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    p = tmp_path / name
    wb.save(p)
    return p


def test_a_matrix_with_semester_lines_and_its_own_headings(tmp_path):
    p = _xlsx(tmp_path, [
        ["JAIN (Deemed-to-be University)"],
        ["Curriculum Matrix — BBA 2027-28"],
        [],
        ["Sl No", "Category", "Course Code", "Course Name", "L", "T", "P", "E", "Credits",
         "CIA", "ESE", "Total"],
        ["Semester I"],
        [1, "Major", "26BBA1C01", "Principles of Management", 3, 1, 0, 0, 4, 50, 50, 100],
        [2, "AEC", "26BBA1A01", "English", 2, 0, 0, 0, 2, 25, 25, 50],
        ["Semester II"],
        [3, "Minor", "26BBA2M01", "Business Analytics", "3", "0", "2", "0", "4", 50, 50, 100],
        ["", "", "", "Total", "", "", "", "", 10, "", "", ""],
    ])
    out = rows_from_file(p, SECTION)
    rows = out["rows"]
    assert len(rows) == 3 and out["skipped"] == 1
    assert rows[0] == {"semester": 1, "nep_category": "Major (Core)", "course_code": "26BBA1C01",
                       "course_title": "Principles of Management", "l": 3, "t": 1, "p": 0, "e": 0,
                       "credits": 4, "cia": 50, "ese": 50, "total_marks": 100}
    assert rows[1]["nep_category"] == "Ability Enhancement Courses (AEC)"
    assert rows[2]["semester"] == 2 and rows[2]["nep_category"] == "Minor Stream" and rows[2]["p"] == 2


def test_a_semester_column_in_roman_numerals(tmp_path):
    p = _xlsx(tmp_path, [
        ["Semester", "Course title", "Credits"],
        ["III", "Marketing", 4],
        ["Sem 4", "Finance", "3"],
    ])
    rows = rows_from_file(p, SECTION)["rows"]
    assert [r["semester"] for r in rows] == [3, 4]


def test_a_csv_works_too(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Semester,Course Code,Course Title,L,T,P,E,Credits\n1,C1,Accounts,3,0,0,0,3\n")
    rows = rows_from_file(p, SECTION)["rows"]
    assert rows == [{"semester": 1, "course_code": "C1", "course_title": "Accounts",
                     "l": 3, "t": 0, "p": 0, "e": 0, "credits": 3}]


def test_old_xls_and_unmatched_files_say_why(tmp_path):
    old = tmp_path / "m.xls"
    old.write_bytes(b"\xd0\xcf\x11\xe0 old excel")
    with pytest.raises(ImportError_, match="xlsx"):
        rows_from_file(old, SECTION)
    p = _xlsx(tmp_path, [["Name", "Phone"], ["A", "1"]], "other.xlsx")
    with pytest.raises(ImportError_, match="header row"):
        rows_from_file(p, SECTION)


def test_the_route_reads_an_uploaded_file(app, client, tmp_path):
    from test_workflow import login, make_department
    u, pw = make_department(app)
    with app.app_context():
        from app.db import get_db
        get_db().settings.update_one({"_id": "app"}, {"$set": {"dev_mode": True}}, upsert=True)
    login(client, u, pw)
    p = _xlsx(tmp_path, [["Semester", "Course Code", "Course Title", "Credits"],
                         [1, "C1", "Accounts", 4]])
    up = client.post("/department/api/upload", data={
        "file": (io.BytesIO(p.read_bytes()), "matrix.xlsx"), "stage": "prog_curriculum",
        "field": "document"}, content_type="multipart/form-data").get_json()
    assert up["ok"], up
    r = client.post("/department/api/prog_curriculum/BCMREG/import/semester_structure",
                    json={"stored": up["stored"]})
    # the programme may not exist for this test department; the route still
    # guards it — try the catalogue's first programme instead when needed
    j = r.get_json()
    if r.status_code == 404 and "programme" in (j.get("error") or "").lower():
        from app.workflow import get_or_create_submission, programmes_of
        with app.app_context():
            from app.db import get_db
            dept = get_db().departments.find_one({"dept_code": "COM"})
            progs = programmes_of(get_or_create_submission("COM", "2027-28"), dept)
        if not progs:
            pytest.skip("no programme for the test department")
        r = client.post(f"/department/api/prog_curriculum/{progs[0]['programme_code']}"
                        "/import/semester_structure", json={"stored": up["stored"]})
        j = r.get_json()
    assert j["ok"], j
    assert j["rows"] == [{"semester": 1, "course_code": "C1", "course_title": "Accounts", "credits": 4}]


def test_only_tables_that_take_a_file_can_be_filled(app, client):
    from test_workflow import login, make_department
    u, pw = make_department(app)
    login(client, u, pw)
    r = client.post("/department/api/dept_info/import/identity", json={"stored": "x"})
    assert r.status_code == 404
