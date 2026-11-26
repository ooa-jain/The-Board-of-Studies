"""Sync from Drive fills a programme whose page was opened before: the blank
row the page starts with (and saves) is not a course of its own."""

from test_packs import _signed_in_department, _sub


def test_sync_fills_a_programme_that_holds_only_a_blank_row(app, client):
    code = _signed_in_department(app, client)
    blank = {"semester": None, "nep_category": "", "course_code": "", "course_title": "", "total_marks": 100}
    assert client.post("/department/api/prog_curriculum/BCAAIN/save",
                       json={"semester_structure": [blank], "details": {}, "profile": {}}).get_json()["ok"]
    assert client.post("/department/api/prog_syllabus/BCAAIN/save",
                       json={"courses": [{"course_code": "", "course_title": ""}]}).get_json()["ok"]
    client.post("/department/drive/fill", follow_redirects=True)
    parts = _sub(app, code)["programmes"]["BCAAIN"]
    rows = parts["prog_curriculum"]["data"]["semester_structure"]
    assert len(rows) > 20 and all(r.get("course_code") and r.get("course_title") for r in rows)
    courses = parts["prog_syllabus"]["data"]["courses"]
    assert len(courses) > 20 and all(c.get("course_title") for c in courses)
    assert parts["prog_revision"]["data"]["courses"]


def test_a_pack_loads_over_a_blank_row_but_not_over_real_courses(app):
    from app.packs import has_content, real_rows
    assert real_rows([{"course_code": "", "course_title": " "}, {}]) == []
    assert not has_content("prog_curriculum", {"semester_structure": [{"course_code": ""}]})
    assert has_content("prog_curriculum", {"semester_structure": [{"course_code": "25MCA101"}]})
    assert has_content("prog_syllabus", {"courses": [{"course_title": "Data Structures"}]})
