"""A PDF's keywords are checked, and Train learns from it, as a Word file's
are — and when its text cannot be read, the reason is given: a scanned copy
(no text layer), or a server that cannot read PDFs yet."""

import io
from pathlib import Path

from test_workflow import DEPT_INFO_OK, login, make_department


def _pdf(path, lines=()):
    """A PDF with these lines as text, or a blank page (a scan has no text either)."""
    import pypdfium2 as pdfium
    if not lines:
        d = pdfium.PdfDocument.new()
        d.new_page(300, 300)
        d.save(str(path))
        d.close()
        return path
    from app.demo_dept import _pdf as demo_pdf
    path.write_bytes(demo_pdf(list(lines)))
    return path


def test_a_text_pdf_is_read_and_a_scan_is_named(tmp_path):
    from app.keyword_match import check, read_text, suggest, why_unread
    pdf = _pdf(tmp_path / "minutes.pdf", ["Minutes of the Pre-BoS meeting", "Agenda: course matrix",
                                          "Lesson plan audit reviewed", "Lesson plan audit approved",
                                          "Members present: 9"])
    assert read_text(pdf) and check(pdf, "pre_bos_minutes", "Minutes of the Meeting (Pre-BoS)")["status"] == "match"
    assert "Lesson plan" in [s["word"] for s in suggest(read_text(pdf), [])]
    scan = _pdf(tmp_path / "scan.pdf")
    m = check(scan, "pre_bos_minutes", "Minutes of the Meeting (Pre-BoS)")
    assert m["status"] == "unread" and m["why"] == "scan" == why_unread(scan)


def test_phrases_stay_within_a_line():
    from app.keyword_match import suggest
    text = "Internal Invitee\n(Depending on the areas)\nInternal Invitee\n(Depending on the areas)\n"
    words = [s["word"] for s in suggest(text, [])]
    assert "Internal Invitee" in words and "Invitee Depending" not in words


def test_a_server_without_the_pdf_reader_says_so(app, client, monkeypatch, tmp_path):
    from app import keyword_match
    monkeypatch.setattr(keyword_match, "pdf_reader_ok", lambda: False)
    assert keyword_match.why_unread(Path(tmp_path / "x.pdf")) == "no_reader"

    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    monkeypatch.setattr(keyword_match, "read_text", lambda path, limit=60000: None)
    blank = _pdf(tmp_path / "scan.pdf")
    up = client.post("/department/api/upload", data={
        "file": (io.BytesIO(blank.read_bytes()), "minutes.pdf"), "stage": "pre_bos", "field": "pre_bos_minutes"},
        content_type="multipart/form-data").get_json()
    assert up["match"]["status"] == "unread" and up["match"]["why"] == "no_reader"
    client.get("/logout")

    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    r = client.post("/admin/keywords/train", json={"dept_code": "COM", "stored": up["stored"]}).get_json()
    assert r["unread"] and r["why"] == "no_reader"
    page = client.get("/admin/keywords").get_data(as_text=True)
    assert "PDFs cannot be read on this server yet" in page and "pip install -r requirements.txt" in page
