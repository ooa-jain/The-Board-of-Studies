"""
Share links — what the Excel and Word downloads link to.

Like a Drive "anyone with the link" share: the link opens a document or a
programme report without signing in — unless the Office has set the links
to "signed-in team only" (Settings › Team & access), when it opens only for
someone signed in who may see that department: the Office's team within
their departments, or the department itself. Each link carries a code signed with the
portal's SECRET_KEY naming exactly one file (or one programme's report), so
it cannot be edited to reach anything else; changing SECRET_KEY withdraws
every link at once.

    /share/d/<token>        the document, shown in the browser: a PDF or a
                            picture as is, a Word document or an Excel sheet
                            turned into a readable page, with Download
    /share/d/<token>/file   the file itself
    /share/r/<token>        a programme's report
    /share/c/<token>        a programme's Curriculum in the Office's
                            curriculum template (app/docgen.py), shown on
                            the page; /file downloads the Word document
    /share/s/<token>        its Syllabus, in the syllabus template, the same way
    /share/v/<token>        its Course Revision, in the syllabus revision template
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request, send_file, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from .db import get_db

bp = Blueprint("share", __name__)

PDF_OR_PICTURE = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _signer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="share-link-v1")


def doc_token(dept_code, stored):
    return _signer().dumps(["d", dept_code, stored])


def report_token(dept_code, programme_code, year):
    return _signer().dumps(["r", dept_code, programme_code, year])


def generated_token(kind, dept_code, programme_code, year):
    """kind "c" (curriculum) or "s" (syllabus)."""
    return _signer().dumps([kind, dept_code, programme_code, year])


def _read(token, kind):
    try:
        data = _signer().loads(token)
    except BadSignature:
        abort(404)
    if not isinstance(data, list) or not data or data[0] != kind:
        abort(404)
    _gate(data[1])
    return data[1:]


def _gate(dept_code):
    """With the links set to the signed-in team only: sign in first, then
    open it only for those who may see the department."""
    from flask import redirect, session
    from .db import settings
    if settings().get("share_links") != "team":
        return
    u = session.get("user") or {}
    if not u:
        abort(redirect(url_for("auth.login", next=request.full_path.rstrip("?"))))
    if u.get("role") == "department":
        if u.get("dept_code") != dept_code:
            abort(403)
        return
    from .access import allows, current_user, may_see
    if not (allows(current_user(), "overview", "view") or allows(current_user(), "documents", "view")) \
            or not may_see(dept_code):
        abort(403)


def _file(token):
    dept_code, stored = _read(token, "d")
    rec = get_db().files.find_one({"dept_code": dept_code, "stored_name": stored}) or abort(404)
    path = (current_app.config["UPLOAD_ROOT"] / (rec.get("academic_year") or "")
            / dept_code / rec["stage"] / stored)
    if not path.is_file():
        abort(404)
    return rec, path


@bp.route("/d/<token>/file")
def doc_file(token):
    rec, path = _file(token)
    suffix = Path(rec["original_name"]).suffix.lower()
    inline = suffix in PDF_OR_PICTURE and request.args.get("download") != "1"
    return send_file(path, as_attachment=not inline, download_name=rec["original_name"])


@bp.route("/d/<token>")
def doc(token):
    rec, path = _file(token)
    suffix = Path(rec["original_name"]).suffix.lower()
    kind, body = "download", None
    if suffix == ".pdf":
        kind = "pdf"
    elif suffix in PDF_OR_PICTURE:
        kind = "image"
    elif suffix == ".docx":
        kind, body = "docx", _docx_blocks(path)
    elif suffix in (".xlsx", ".xlsm"):
        kind, body = "xlsx", _xlsx_sheets(path)
    dept = get_db().departments.find_one({"dept_code": rec["dept_code"]}) or {}
    return render_template("share/doc.html", rec=rec, dept=dept, kind=kind, body=body,
                           file_url=url_for("share.doc_file", token=token),
                           download_url=url_for("share.doc_file", token=token, download=1),
                           hide_chrome=True)


@bp.route("/r/<token>")
def report(token):
    from .report import ShareLinks, programme_context
    dept_code, programme_code, year = _read(token, "r")
    db = get_db()
    dept = db.departments.find_one({"dept_code": dept_code}) or abort(404)
    ctx = programme_context(db, dept, year, programme_code, ShareLinks(dept_code, year)) or abort(404)
    return render_template("admin/programme_report.html", shared=True, **ctx)


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# the documents generated for a programme, by the letter in their links
GENERATED = {"c": "Curriculum", "s": "Syllabus", "v": "Course Revision"}
ENDPOINTS = {"c": "share.curriculum", "s": "share.syllabus", "v": "share.revision"}


def generated_docx(kind, dept_code, programme_code, year):
    """(buffer, file name) for a programme's generated Curriculum, Syllabus or
    Course Revision, or None."""
    from .docgen import curriculum_docx, revision_docx, syllabus_docx
    make = {"c": curriculum_docx, "s": syllabus_docx, "v": revision_docx}[kind]
    buf = make(get_db(), dept_code, year, programme_code)
    if buf is None:
        return None
    return buf, f"{programme_code}-{GENERATED[kind].replace(' ', '-')}-{year}.docx"


@bp.route("/c/<token>", endpoint="curriculum", defaults={"kind": "c"})
@bp.route("/s/<token>", endpoint="syllabus", defaults={"kind": "s"})
@bp.route("/v/<token>", endpoint="revision", defaults={"kind": "v"})
def generated(token, kind):
    """The generated Curriculum or Syllabus, shown on the page as the Word
    document lays it out, with a Download button."""
    from .docgen import to_view
    dept_code, programme_code, year = _read(token, kind)
    out = generated_docx(kind, dept_code, programme_code, year) or abort(404)
    dept = get_db().departments.find_one({"dept_code": dept_code}) or {}
    return render_template("share/generated.html", view=to_view(out[0]), dept=dept, year=year,
                           title=GENERATED[kind],
                           programme_code=programme_code, file_name=out[1],
                           download_url=url_for(request.endpoint, token=token) + "/file",
                           hide_chrome=True)


@bp.route("/c/<token>/file", endpoint="curriculum_file", defaults={"kind": "c"})
@bp.route("/s/<token>/file", endpoint="syllabus_file", defaults={"kind": "s"})
@bp.route("/v/<token>/file", endpoint="revision_file", defaults={"kind": "v"})
def generated_file(token, kind):
    dept_code, programme_code, year = _read(token, kind)
    out = generated_docx(kind, dept_code, programme_code, year) or abort(404)
    return send_file(out[0], as_attachment=True, download_name=out[1], mimetype=DOCX)


# ---------------------------------------------------------------------------
# Word and Excel, as a page the browser can show
# ---------------------------------------------------------------------------

def _docx_blocks(path, limit=4000):
    """Paragraphs and tables in document order: [("h"|"p", text) | ("table", rows)]."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        doc = Document(path if hasattr(path, "read") else str(path))
    except Exception:
        return None
    out = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            text = p.text.strip()
            if text:
                style = (p.style.name if p.style is not None else "") or ""
                out.append(("h" if style.lower().startswith(("heading", "title")) else "p", text))
        elif tag == "tbl":
            rows = []
            for row in Table(child, doc).rows:
                cells, last = [], None
                for c in row.cells:            # merged cells repeat; show them once
                    if c._tc is last:
                        continue
                    last = c._tc
                    cells.append(c.text.strip())
                rows.append(cells)
            if rows:
                out.append(("table", rows))
        if len(out) >= limit:
            break
    return out


def _xlsx_sheets(path, max_rows=600, max_cols=40):
    from openpyxl import load_workbook
    try:
        wb = load_workbook(path if hasattr(path, "read") else str(path), read_only=True, data_only=True)
    except Exception:
        return None
    sheets = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(max_col=max_cols, values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            if any(v.strip() for v in vals):
                rows.append(vals)
            if len(rows) >= max_rows:
                break
        # columns empty in every row are layout, not content
        width = max((len(r) for r in rows), default=0)
        keep = [i for i in range(width) if any(i < len(r) and r[i].strip() for r in rows)]
        sheets.append({"name": ws.title,
                       "rows": [[r[i] if i < len(r) else "" for i in keep] for r in rows]})
    wb.close()
    return sheets
