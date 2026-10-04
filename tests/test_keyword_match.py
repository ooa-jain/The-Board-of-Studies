"""Right after an upload, the file is searched for the words a document for
its box always carries, and the answer comes back with the upload."""

import io
import zipfile

from test_summaries import _minutes_pdf, _upload
from test_workflow import _tiny_pdf, login, make_department


def _docx(text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   "<w:document><w:body>" + "".join(
                       f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\n"))
                   + "</w:body></w:document>")
    return buf.getvalue()


def test_minutes_carry_the_words_minutes_carry(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "minutes.pdf", _minutes_pdf(), field="minutes")
    assert j["ok"]
    m = j["match"]
    assert m["status"] == "match", m
    assert "minutes" in m["found"] and "resolved" in m["found"]


def test_the_wrong_file_in_a_box_is_called_out(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "minutes.pdf", _minutes_pdf(), field="external_profiles")
    assert j["match"]["status"] in ("miss", "weak"), j["match"]


def test_a_word_document_is_read_too(app, client):
    u, p = make_department(app)
    login(client, u, p)
    body = "Department Vision\nOur mission is to teach well.\nProgramme overview and objectives."
    j = _upload(client, "vm.docx", _docx(body), field="vision_mission")
    assert j["match"]["status"] == "match"
    j = _upload(client, "vm.docx", _docx("A shopping list: milk, bread, eggs and tea."), field="vision_mission")
    assert j["match"]["status"] == "miss"


def test_a_file_with_no_text_is_not_judged(app, client):
    u, p = make_department(app)
    login(client, u, p)
    j = _upload(client, "scan.pdf", _tiny_pdf(), field="attendance")
    assert j["match"]["status"] == "unread"
