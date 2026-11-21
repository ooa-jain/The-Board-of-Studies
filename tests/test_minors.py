"""Specialisation: the major, and the minors on offer (+ Add minor), each a
list of courses in Annexure I; the Word file lays Annexure I out as the
Course Matrix does — a semester a row, a Code and Title pair per minor.
Reservation is filled by the Office."""

import io

from docx import Document

from test_workflow import login, make_department


def test_details_ask_for_the_major_and_the_minors():
    from app.schema import STAGE_BY_KEY
    stage = STAGE_BY_KEY["prog_curriculum"]
    details = next(s for s in stage["sections"] if s["key"] == "details")
    f = {x["name"]: x for x in details["fields"]}
    assert f["specialisation"]["label"] == "Specialisation (Major)"
    assert f["minor_streams"]["type"] == "name_list"
    minors = next(s for s in stage["sections"] if s["key"] == "minors")
    assert minors["buckets_from"] == "details.minor_streams" and minors["bucket_field"] == "minor_title"
    profile = next(s for s in stage["sections"] if s["key"] == "profile")
    res = next(x for x in profile["fields"] if x["name"] == "reservation_policy")
    assert res["type"] == "fixed" and res["office_filled"] and "Office of Academic Affairs" in res["help"]


def test_a_minor_named_twice_is_an_error(app, client):
    u, p = make_department(app)
    login(client, u, p)
    body = client.post("/department/api/prog_curriculum/BCMREG/validate",
                       json={"details": {"minor_streams": ["Analytics", "analytics"]}}).get_json()
    assert any("listed twice" in i["message"] for i in body.get("issues", []) if i.get("section") == "details")


def test_item_nine_names_the_minors():
    from app.workflow import apply_defaults
    data = apply_defaults("prog_curriculum", {
        "details": {"programme_name": "BCom (Corporate Finance)", "specialisation": "Corporate Finance",
                    "minor_streams": ["Analytics", "Digital Marketing"], "degree_level": "UG - 3 Year"}})
    assert data["profile"]["course_specialisation"].endswith("Corporate Finance — Minors: Analytics / Digital Marketing")


def test_annexure_one_a_column_pair_per_minor():
    from unittest import mock

    import mongomock

    from app import docgen
    cur = {"details": {"programme_name": "BCom (Corporate Finance)", "specialisation": "Corporate Finance",
                       "minor_streams": ["Analytics", "Digital Marketing"], "batch": "2026-30"},
           "semester_structure": [{"semester": 1, "nep_category": "Major (Core)", "course_code": "26BCC1C01",
                                   "course_title": "Basics Financial Accounting", "credits": 4,
                                   "cia": 50, "ese": 50, "total_marks": 100}],
           "minors": [{"minor_title": "Analytics", "semester": 2, "course_code": "26BAL2M01",
                       "course_title": "Introduction to Business Analytics", "credits": 4},
                      {"minor_title": "Analytics", "semester": 6, "course_code": "26BAL6M01L",
                       "course_title": "Predictive Analytics", "credits": 4},
                      {"minor_title": "Analytics", "semester": 6, "course_code": "26BAL6M02",
                       "course_title": "Business Intelligence", "credits": 4},
                      {"minor_title": "Digital Marketing", "semester": 2, "course_code": "26BDM2M01",
                       "course_title": "Fundamentals of Digital Marketing", "credits": 4}]}
    with mock.patch.object(docgen, "programme_record",
                           return_value=({"dept_code": "COM"}, {"programme_code": "BC"}, cur, None)), \
            mock.patch("app.schema.is_flow", return_value=False):
        out = docgen.curriculum_docx(mongomock.MongoClient().db, "COM", "2027-28", "BC")
    doc = Document(io.BytesIO(out.getvalue() if hasattr(out, "getvalue") else out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Analytics / Digital Marketing" in text
    annex = next(t for t in doc.tables if "Annexure" in t.rows[0].cells[0].text)
    heads = [c.text for c in annex.rows[1].cells]
    assert "ANALYTICS" in heads and "DIGITAL MARKETING" in heads
    assert [c.text for c in annex.rows[2].cells][:3] == ["Semester", "Course Code", "COURSE TITLE"]
    body = [[c.text for c in r.cells] for r in annex.rows[3:]]
    # semester 2: both minors on one row; semester 6: Analytics' two courses on two rows
    assert body[0][:5] == ["2", "26BAL2M01", "Introduction to Business Analytics", "26BDM2M01",
                           "Fundamentals of Digital Marketing"]
    assert [r[0] for r in body] == ["2", "6", "6"]


def test_an_earlier_batch_has_minors_as_the_current_batch():
    from app.schema import BATCH_PARTS, for_level
    part = BATCH_PARTS[14]                      # Batch of 2024–2025
    keys = [s["key"] for s in part["sections"]]
    assert keys.index("batch_courses") < keys.index("details") < keys.index("minors") < keys.index("courses")
    details = next(s for s in part["sections"] if s["key"] == "details")
    assert [f["name"] for f in details["fields"]] == ["specialisation", "minor_streams"]
    minors = next(s for s in part["sections"] if s["key"] == "minors")
    assert minors["buckets_from"] == "details.minor_streams"
    # a PG programme has none
    pg = for_level(part, "PG - 2 Year")
    assert "minors" not in [s["key"] for s in pg["sections"]]
    assert [f["name"] for f in next(s for s in pg["sections"] if s["key"] == "details")["fields"]] == ["specialisation"]


def test_an_earlier_batch_word_file_lists_its_minors():
    from unittest import mock

    import mongomock

    from app import docgen
    from app.schema import BATCH_PARTS
    part = BATCH_PARTS[14]["key"]
    data = {"details": {"specialisation": "Corporate Finance", "minor_streams": ["Analytics"]},
            "batch_courses": [{"semester": 1, "nep_category": "Major (Core)", "course_code": "24BCC1C01",
                               "course_title": "Accounting", "credits": 4, "cia": 50, "ese": 50,
                               "total_marks": 100}],
            "minors": [{"minor_title": "Analytics", "semester": 2, "course_code": "24BAL2M01",
                        "course_title": "Business Analytics", "credits": 4}]}
    with mock.patch.object(docgen, "programme_record",
                           return_value=({"dept_code": "COM"}, {"programme_code": "BC", "programme_name": "BCom",
                                                                "degree_level": "UG - 3 Year"}, {}, None)), \
            mock.patch.object(docgen, "_earlier", return_value=(data, [1, 2], "Batch of 2024–2025")), \
            mock.patch("app.schema.is_flow", return_value=False):
        out = docgen.batch_curriculum_docx(mongomock.MongoClient().db, "COM", "2027-28", "BC", part)
    doc = Document(io.BytesIO(out.getvalue() if hasattr(out, "getvalue") else out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Analytics" in text and "Corporate Finance" in text
    annex = next(t for t in doc.tables if "Annexure" in t.rows[0].cells[0].text)
    assert "Business Analytics" in [c.text for r in annex.rows for c in r.cells]
