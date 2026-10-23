"""Each syllabus module names the level of Bloom's Taxonomy it reaches — one
of BTA 1 (Remembering) to BTA 6 (Creating) — beside its CO's, on the page
and in the Word syllabus."""

import io

from test_workflow import login


def test_a_modules_bta_level_is_kept_and_printed(app, client):
    from docx import Document

    from app import demo_dept
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    data = client.get("/department/api/record?programme=DEMOBBA").get_json()["items"][1]["data"]
    data["courses"][0]["modules"][0].update(cos=["CO1", "CO2"], bta="BTA 3 (Applying)")
    assert client.post("/department/api/prog_syllabus/DEMOBBA/save", json=data).get_json()["ok"]

    # the page offers the six levels, one to choose
    js = client.get("/static/js/stage.js").get_data(as_text=True)
    for level in ("BTA 1 (Remembering)", "BTA 2 (Understanding)", "BTA 3 (Applying)",
                  "BTA 4 (Analyzing)", "BTA 5 (Evaluating)", "BTA 6 (Creating)"):
        assert level in js

    # the Word syllabus: a BTA column after CO's, with the module's level
    from app.db import get_db
    from app.docgen import syllabus_docx
    with app.app_context():
        doc = Document(io.BytesIO(syllabus_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    rows = [[c.text for c in r.cells] for r in doc.tables[0].rows]
    head = next(r for r in rows if "CO's" in r)
    assert head.index("BTA") == head.index("CO's") + 1
    first = next(r for r in rows if r[0].startswith("Module No. 1"))
    assert "CO1, CO2" in first and "BTA 3 (Applying)" in first
