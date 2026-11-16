"""Course categories: Major shown as Core Course (CC), and AEC (Language) —
one row with a code and title for each language and one set of L-T-P-E,
credits and marks."""

import json

from test_workflow import login, make_department

LANG = "Ability Enhancement Courses (AEC) - Language"


def _row(cat, code, title, cr, sem=1):
    return {"semester": sem, "nep_category": cat, "course_code": code, "course_title": title,
            "l": cr, "t": 0, "p": 0, "e": 0, "credits": cr, "cia": 50, "ese": 50, "total_marks": 100}


def test_categories_offer_cc_and_aec_language():
    from app.schema import CATEGORY_LABELS, NEP_CATEGORIES, course_category
    from app.ugc_rules import NEP_CATEGORY_TO_KEY
    assert NEP_CATEGORIES[0] == "Major (Core)" and CATEGORY_LABELS["Major (Core)"] == "Major / Core Course (CC)"
    assert LANG in NEP_CATEGORIES and CATEGORY_LABELS[LANG] == "Ability Enhancement / AEC (Language)"
    assert NEP_CATEGORY_TO_KEY[LANG] == "aec"
    assert course_category(LANG) == LANG          # kept as it is, not read as another group


def test_language_row_is_one_set_of_credits_and_a_syllabus_per_language(app, client):
    from app.db import get_db
    from app.validation import _category_credits
    from app.workflow import course_fill_source
    u, p = make_department(app)
    login(client, u, p)
    rows = [_row("Major (Core)", "26BC1", "Accounting", 4),
            _row(LANG, "26LK1 / 26LH1 / 26LF1", "Kannada / Hindi / French", 3),
            _row("Ability Enhancement Courses (AEC)", "26AE1", "English", 2)]
    client.post("/department/api/prog_curriculum/BCMREG/save", json={"semester_structure": rows})
    page = client.get("/department/stage/prog_curriculum/BCMREG").get_data(as_text=True)
    data = json.loads(page.split('id="stage-data" type="application/json">')[1].split("</script>")[0])
    assert data["semester_structure"][1]["nep_category"] == LANG

    # AEC credits: the language row once (3) and English (2)
    assert _category_credits({"semester_structure": rows}, {})["aec"] == 5

    body = client.post("/department/api/prog_curriculum/BCMREG/validate",
                       json={"semester_structure": rows}).get_json()
    bad = [i["message"] for i in body.get("issues", []) if i.get("section") == "semester_structure"
           and i.get("row") == 1 and i["level"] == "error"]
    assert not bad, bad

    with app.app_context():
        sub = get_db().submissions.find_one({"dept_code": "COM"})
        courses = {c["course_code"]: c["course_title"] for c in course_fill_source(sub, "BCMREG")}
    assert courses["26LK1"] == "Kannada" and courses["26LH1"] == "Hindi" and courses["26LF1"] == "French"
