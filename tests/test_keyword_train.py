"""Train: beside each file in the Office's review, the words that file
carries often that its upload box's keywords do not have yet — the Office
ticks the right ones and adds them; the file is checked again."""

import io

from test_workflow import DEPT_INFO_OK, login, make_department


def _docx(text):
    import docx
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_the_suggestions_are_new_words_the_file_uses_often():
    from app.keyword_match import KEYWORDS, add_keywords, suggest
    text = ("Composition of Board of Studies\nCategory Role Name Designation\n"
            "Subject Expert  External Member  Dr. Anil  Professor\nSubject Expert  External Member  Ms. Kavya  Design Lead\n"
            "Subject Expert nominated by the Vice Chancellor. Design Lead from the industry.\n")
    words = [s["word"] for s in suggest(text, KEYWORDS["bos_composition"])]
    assert "Subject Expert" in words and "External Member" in words and "Design Lead" in words
    assert "Expert External" not in words                    # two table cells read across
    assert not {"Board", "Studies", "Category"} & set(words)  # in the list already
    # adding: none twice, whatever the case
    assert add_keywords(["vision", "mission / goals"], ["Mission", "Subject Expert", "subject expert"]) == \
        ["vision", "mission / goals", "Subject Expert"]


def test_the_office_trains_a_box_from_a_departments_file(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    up = client.post("/department/api/upload", data={
        "file": (io.BytesIO(_docx("Minutes of the Pre-BoS meeting\nAgenda and minutes\n"
                                  "Programme Outcome attainment reviewed. Programme Outcome attainment approved.\n"
                                  "Lesson plan audit done. Lesson plan audit signed.")), "pre-bos.docx"),
        "stage": "pre_bos", "field": "pre_bos_minutes"}, content_type="multipart/form-data").get_json()
    assert client.post("/department/api/pre_bos/save",
                       json={"pre_bos_files": {"pre_bos_minutes": up}}).get_json()["ok"]
    client.get("/logout")

    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    j = client.get("/admin/submissions/COM/review/pre_bos").get_json()
    assert j["train_url"] == "/admin/keywords/train" and j["train_add_url"] == "/admin/keywords/add"
    r = client.post(j["train_url"], json={"dept_code": "COM", "stored": up["stored"]}).get_json()
    assert r["ok"] and r["field"] == "pre_bos_minutes" and not r["unread"]
    words = [s["word"] for s in r["suggestions"]]
    assert "Programme Outcome" in words and "Lesson plan" in words
    # the Office approves two of them
    a = client.post(j["train_add_url"], json={"field": "pre_bos_minutes", "words": ["Programme Outcome", "Lesson plan"],
                                              "dept_code": "COM", "stored": up["stored"]}).get_json()
    assert a["ok"] and a["added"] == ["Programme Outcome", "Lesson plan"]
    assert "Programme Outcome" in a["match"]["found"]                     # the file, checked again
    from app.db import get_db
    with app.app_context():
        kw = get_db().settings.find_one({"_id": "app"})["keywords"]["pre_bos_minutes"]
    assert kw[-2:] == ["Programme Outcome", "Lesson plan"]
    assert "Programme Outcome" in client.get("/admin/keywords").get_data(as_text=True)
    # nothing ticked, or a file not on record, is refused
    assert client.post(j["train_add_url"], json={"field": "pre_bos_minutes", "words": []}).status_code == 400
    assert client.post(j["train_url"], json={"dept_code": "COM", "stored": "nope"}).status_code == 404
