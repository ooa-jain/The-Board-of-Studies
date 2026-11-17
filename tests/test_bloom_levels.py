"""Each syllabus module names the level of Bloom's Taxonomy it reaches — one
of BTL 1 (Remembering) to BTL 6 (Creating) — beside its COs, on the page
and in the Word syllabus. (It was called BTA; a syllabus saved then reads as BTL.)"""

import io

from test_workflow import login


def test_a_modules_btl_level_is_kept_and_printed(app, client):
    from docx import Document

    from app import demo_dept
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    data = client.get("/department/api/record?programme=DEMOBBA").get_json()["items"][1]["data"]
    data["courses"][0]["modules"][0].update(cos=["CO1", "CO2"], bta="BTL 3 (Applying)")
    # a module saved when it was called BTA
    data["courses"][0]["modules"][1].update(cos=["CO3"], bta="BTA 4 (Analyzing)")
    assert client.post("/department/api/prog_syllabus/DEMOBBA/save", json=data).get_json()["ok"]

    # the page offers the six levels, one to choose
    js = client.get("/static/js/stage.js").get_data(as_text=True)
    for level in ("BTL 1 (Remembering)", "BTL 2 (Understanding)", "BTL 3 (Applying)",
                  "BTL 4 (Analyzing)", "BTL 5 (Evaluating)", "BTL 6 (Creating)"):
        assert level in js
    # headed COs and BTL — no apostrophe, and not BTA
    assert '["COs"]' in js and '["BTL"]' in js and "\"CO's\"" not in js and '["BTA"]' not in js

    # the Word syllabus: each module's line names its COs and its level, as the sample lays it out
    from app.db import get_db
    from app.docgen import syllabus_docx
    with app.app_context():
        doc = Document(io.BytesIO(syllabus_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    first = next(p.text for p in doc.paragraphs if p.text.startswith("Module 1:"))
    assert "(CO1, CO2; BTL 3 (Applying))" in first and first.endswith("Hours")
    second = next(p.text for p in doc.paragraphs if p.text.startswith("Module 2:"))
    assert "(CO3; BTL 4 (Analyzing))" in second and "BTA" not in second

