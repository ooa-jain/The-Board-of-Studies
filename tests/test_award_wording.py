"""Item 12 names the programme, its major specialisation in brackets; the
Reservation block is greyed out; the pencil beside each programme."""

from app.schema import DEFAULT_REGULATIONS, award_wording, programme_field

BCA_AIML = ("Bachelor of Computer Applications (Honours / Honours with Research) "
            "with specialisation in Artificial Intelligence and Machine Learning")


def test_the_programme_field_from_its_name():
    assert programme_field(BCA_AIML) == "Computer Applications"
    assert programme_field("Bachelor of Commerce (Honours / Honours with Research)") == "Commerce"
    assert programme_field("") == ""


def test_item_12_names_the_programme_and_its_major_in_brackets():
    text = award_wording(DEFAULT_REGULATIONS["award"], BCA_AIML, "Artificial Intelligence and Machine Learning")
    assert "The Bachelor's degree in Computer Applications (Artificial Intelligence and Machine Learning), " \
           "with the applicable Minor" in text
    assert "in the programme" not in text
    # no major given: the programme alone; no programme: the wording as it is
    assert "in Commerce, with the applicable Minor" in award_wording(
        DEFAULT_REGULATIONS["award"], "Bachelor of Commerce (Honours)", "")
    assert award_wording(DEFAULT_REGULATIONS["award"], "", "") == DEFAULT_REGULATIONS["award"]


def test_the_word_file_item_12_follows_the_programme(app, client):
    import io

    from docx import Document

    from app import demo_dept
    from app.db import get_db
    from app.docgen import curriculum_docx
    from test_workflow import login
    with app.app_context():
        user, pw = demo_dept.create(app.config["ACADEMIC_YEAR"], app.config["UPLOAD_ROOT"])
    login(client, user, pw)
    client.post("/department/demo/fill-all")
    with app.app_context():
        get_db().submissions.update_one({"dept_code": "DEMO"}, {"$unset": {
            "programmes.DEMOBBA.prog_curriculum.data.profile.award": ""},
            "$set": {"programmes.DEMOBBA.prog_curriculum.data.details.specialisation": "Corporate Finance"}})
        doc = Document(io.BytesIO(curriculum_docx(get_db(), "DEMO", app.config["ACADEMIC_YEAR"], "DEMOBBA").getvalue()))
    text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "(Corporate Finance), with the applicable Minor" in text


def test_the_reservation_block_is_greyed_out_and_the_programme_dropdown_has_a_pencil():
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "app/static/js/stage.js").read_text()
    css = (Path(__file__).resolve().parent.parent / "app/static/css/app.css").read_text()
    assert 'office_filled ? " is-greyed"' in js and ".fixed-block.is-greyed" in css
    assert 'el("button", "pd-edit")' in js and '"Save changes"' in js
