"""Does an uploaded file look like what its box asks for?

Right after an upload the file's text is read (a PDF's text layer, a Word
document's paragraphs, an Excel sheet's cells) and searched for the words a
document of that kind always carries — minutes say "minutes" and "resolved",
an attendance sheet says "attendance" and "signature". The answer goes back
with the upload, so the box can say at once "Keywords match" or "None of
the expected words are in this file — is it the right one?".

It is a quick check, not a verdict: nothing is refused on it.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

# per upload box: the words a right document carries; any one is a match,
# more is better
KEYWORDS = {
    # from the university's templates: their title and categories
    "diac_signed": ["DIAC / Industry-Academia", "Dean / Director", "Head of Department / HOD",
                    "Area Chair / Area Head", "Program Head / Programme Head / Co-Ordinator",
                    "Placement", "Industry", "Alumni", "Designation"],
    "dpac_signed": ["Program Assessment Committee / Programme Assessment Committee / PAC / DPAC",
                    "Chairperson", "Co-Chairperson", "Non-Teaching", "Office of Academics / OOA",
                    "Student", "Professor", "Industry", "Alumni", "Parent", "Academician"],
    "bos_composition": ["board of studies / BoS", "composition", "member", "chairperson / chairman / chair",
                        "external"],
    "vision_mission": ["vision", "mission", "programme overview / program overview / overview",
                       "objectives / outcomes / PEO / PSO"],
    "minutes": ["minutes / proceedings", "meeting", "resolved / approved / decided", "agenda",
                "members present / present / attendance"],
    "external_profiles": ["profile / curriculum vitae / CV / resume", "experience", "qualification / Ph.D / degree",
                          "designation", "publications"],
    "attendance": ["attendance", "signature / signed", "present", "name", "designation"],
    "feedback_curriculum": ["feedback", "stakeholder / students / alumni / employer / faculty", "curriculum",
                            "survey / questionnaire / response", "rating / scale"],
    "feedback_new_programme": ["feedback", "stakeholder / students / alumni / employer / industry",
                               "new programme / new program / proposed", "survey / questionnaire / response"],
    "course_file": ["syllabus", "course", "module / unit", "credits", "outcomes / CO", "hours"],
    "document": ["curriculum", "semester", "credits", "course code", "course title / course name",
                 "programme structure / program structure / scheme"],
}

STOP = {"the", "and", "for", "with", "from", "this", "that", "upload", "file", "files",
        "scanned", "signed", "only", "department", "documents", "document"}

READABLE = {".pdf", ".docx", ".xlsx", ".csv"}


def upload_boxes():
    """Every upload box in the forms, once each: [{field, label, where}]."""
    from .schema import PARTS, STAGES
    out, seen = [], set()
    for stage in STAGES + PARTS:
        for sec in stage.get("sections", []):
            for f in sec.get("fields", []) + sec.get("columns", []):
                if f.get("type") == "file" and f["name"] not in seen:
                    seen.add(f["name"])
                    label = f.get("label") or f["name"]
                    if f["name"] == "course_file":
                        label = "Course document (syllabus row upload)"
                    out.append({"field": f["name"], "label": label,
                                "where": stage.get("group") or stage.get("title", "")})
    return out


def overrides() -> dict:
    """The admin's own lists, from Admin → Keywords; {} outside a request."""
    try:
        from .db import settings
        return (settings() or {}).get("keywords") or {}
    except Exception:
        return {}


def default_keywords(field: str, label: str) -> list[str]:
    if field in KEYWORDS:
        return KEYWORDS[field]
    words = [w for w in re.findall(r"[A-Za-z]{4,}", label or "") if w.lower() not in STOP]
    return list(dict.fromkeys(words))


def keywords_for(field: str, label: str) -> list[str]:
    """The words to look for: the admin's list, else the box's own list,
    else the label's words."""
    mine = overrides().get(field)
    if mine:
        return mine
    if field in KEYWORDS:
        return KEYWORDS[field]
    words = [w for w in re.findall(r"[A-Za-z]{4,}", label or "") if w.lower() not in STOP]
    return list(dict.fromkeys(words))


def read_text(path: Path, limit: int = 60000) -> str | None:
    """The file's text, or None for a file whose text cannot be read here
    (an image, a zip, an old .doc, a scan with no text layer)."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            from .pdflock import PDF_LOCK
            with PDF_LOCK:
                doc = pdfium.PdfDocument(path)
                try:
                    out = []
                    for i in range(min(len(doc), 30)):
                        tp = doc[i].get_textpage()
                        out.append(tp.get_text_range())
                        tp.close()
                        if sum(map(len, out)) > limit:
                            break
                finally:
                    doc.close()
            text = "\n".join(out)
        elif ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            text = re.sub(r"<w:p[ >]", "\n<w:p ", xml)
            text = re.sub(r"<[^>]+>", "", text)
        elif ext == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            cells = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True, max_row=400):
                    cells.extend(str(c) for c in row if c is not None)
            wb.close()
            text = " ".join(cells)
        elif ext == ".csv":
            text = path.read_text(errors="replace")
        else:
            return None
    except Exception:
        return None
    text = text[:limit]
    return text if len(text.strip()) >= 20 else None


def alternatives(keyword: str) -> list[str]:
    """“programme assessment / program assessment” is one keyword with two
    spellings: either one found counts."""
    return [w.strip() for w in keyword.split("/") if w.strip()] or [keyword]


def _found(word: str, text: str) -> bool:
    return any(_found_one(w, text) for w in alternatives(word))


def _found_one(word: str, text: str) -> bool:
    # short words (BoS, DIAC) must match as a whole word and in capitals
    if (len(word) <= 4 and word.isupper()) or word in ("BoS",):
        return re.search(rf"\b{re.escape(word)}\b", text) is not None
    return re.search(rf"\b{re.escape(word)}", text, re.I) is not None


def check(path: Path, field: str, label: str) -> dict:
    """{status, found, seen, expected, label}: status is "match", "weak",
    "miss" or "unread" (no text to check). `found` holds the keywords that
    were met (as written in the list), `seen` the spelling actually in the file."""
    words = keywords_for(field, label)
    base = {"label": label, "expected": words, "found": [], "seen": []}
    if not words:
        return {**base, "status": "unread"}
    text = read_text(path)
    if text is None:
        return {**base, "status": "unread"}
    found, seen = [], []
    for w in words:
        hit = next((a for a in alternatives(w) if _found_one(a, text)), None)
        if hit:
            found.append(w)
            seen.append(hit)
    status = "match" if len(found) >= 2 or (found and len(words) <= 2) else "weak" if found else "miss"
    out = {**base, "status": status, "found": found, "seen": seen}
    # a box with a university template: is the form itself filled in?
    from .template_check import check as template_check
    tpl = template_check(path, field, text)
    if tpl:
        out["template"] = tpl
    return out
