"""Excel and Word exports of the stored submissions."""

from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import ugc_rules as U
from .db import get_db
from .schema import STAGES
from .workflow import compute_status, programmes_of, progress

NAVY = "0F2A4A"
HEAD = "DCE6F1"      # column heads: a quiet blue-grey
LIGHT = "F3F6FA"

_thin = Side(style="thin", color="D5DEE8")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _head(ws, row, values, fill=NAVY, color="FFFFFF"):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(bold=True, color=color, size=10)
        c.fill = PatternFill("solid", fgColor=fill)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 26


def _autosize(ws, max_width=52):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[letter].width = min(max(12, width + 3), max_width)


def _flat(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return "; ".join(_flat(v) for v in value)
    if isinstance(value, dict):
        if "stored" in value and "name" in value:  # an uploaded file
            return str(value["name"])
        return "; ".join(f"{k}: {_flat(v)}" for k, v in value.items())
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y %H:%M")
    return str(value)


# ---------------------------------------------------------------------------
# Excel — one department, on one sheet
# ---------------------------------------------------------------------------

OK_FILL = PatternFill("solid", fgColor="DFF3E4")
NO_FILL = PatternFill("solid", fgColor="FDE7E7")
LINK_FONT = Font(color="0B4A9E", underline="single", size=10)


def _link(cell, text, url):
    cell.value = text
    if url:
        cell.hyperlink = url
        cell.font = LINK_FONT


def _section_title(ws, row, text, width=7):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, size=12, color="FFFFFF")
    for col in range(1, width + 1):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=NAVY)
    ws.row_dimensions[row].height = 22


def department_excel(dept_code: str, year: str, links=None) -> io.BytesIO:
    """The whole record on one sheet: department, stages with ticks and
    document links, then the UG and PG programmes with a link to each
    programme's report."""
    from .report import build, status_word
    rep = build(get_db(), dept_code, year, links)

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFG", (6, 34, 46, 18, 18, 18, 20)):
        ws.column_dimensions[col].width = w

    ws["A1"] = "JAIN (Deemed-to-be University) — Office of Academics"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ws["A2"] = f"Board of Studies record · {rep['dept'].get('dept_name', dept_code)} · {year}"
    ws["A2"].font = Font(size=11, color="53627A")
    r = 4

    _section_title(ws, r, "Department information")
    r += 1
    for k, v in rep["info"]:
        ws.cell(row=r, column=2, value=k).font = Font(bold=True, size=10)
        ws.cell(row=r, column=3, value=_flat(v))
        r += 1

    r += 1
    _section_title(ws, r, "Stages")
    r += 1
    _head(ws, r, ["", "Stage", "Status", "Submitted on", "Filled", "", ""], fill=HEAD, color=NAVY)
    r += 1
    for st in rep["stages"]:
        done = st["status"] == "submitted"
        ws.cell(row=r, column=1, value="✓" if done else "·").fill = OK_FILL if done else NO_FILL
        ws.cell(row=r, column=2, value=st["title"]).font = Font(bold=True, size=10)
        ws.cell(row=r, column=3, value=status_word(st["status"]))
        ws.cell(row=r, column=4, value=_flat(st["submitted_at"]))
        ws.cell(row=r, column=5, value=f"{st['filled']} of {st['total']}"
                + (f" {st['unit']}" if st.get("unit") else " filled"))
        r += 1

    for st in rep["stages"]:
        if st.get("container"):
            continue
        r += 1
        _section_title(ws, r, f"{st['group']} — {st['title']}  ·  {status_word(st['status'])}")
        r += 1
        if st.get("returned_note"):
            ws.cell(row=r, column=2, value="Returned: " + st["returned_note"]).font = \
                Font(italic=True, color="B42318")
            r += 1
        if not st["items"]:
            ws.cell(row=r, column=2, value="Nothing entered yet.").font = Font(italic=True, color="7A8699")
            r += 1
        for filled, label, text, docs in st["items"]:
            tick = ws.cell(row=r, column=1, value="✓" if filled else "✗")
            tick.fill = OK_FILL if filled else NO_FILL
            tick.alignment = Alignment(horizontal="center")
            ws.cell(row=r, column=2, value=label).alignment = Alignment(wrap_text=True, vertical="top")
            if docs:
                for k, (name, url) in enumerate(docs):
                    if k:
                        r += 1
                    _link(ws.cell(row=r, column=3), name, url)
            else:
                c = ws.cell(row=r, column=3, value=text or "Not filled")
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if not text:
                    c.font = Font(italic=True, color="7A8699")
            r += 1

    for level in ("UG", "PG"):
        progs = rep["programmes"][level]
        r += 1
        _section_title(ws, r, f"{level} programmes ({len(progs)})")
        r += 1
        if not progs:
            ws.cell(row=r, column=2, value="None.").font = Font(italic=True, color="7A8699")
            r += 1
            continue
        _head(ws, r, ["", "Programme", "Code · degree", "Curriculum", "Syllabus", "Course Revision",
                      "Report"], fill=HEAD, color=NAVY)
        r += 1
        for p in progs:
            all_done = all(x["status"] == "submitted" for x in p["parts"])
            ws.cell(row=r, column=1, value="✓" if all_done else "·").fill = OK_FILL if all_done else NO_FILL
            _link(ws.cell(row=r, column=2), p["programme_name"], p["report"])
            ws.cell(row=r, column=2).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=3, value=" · ".join(x for x in (p["programme_code"],
                                                               p.get("degree_level")) if x))
            for i, part in enumerate(p["parts"]):
                c = ws.cell(row=r, column=4 + i, value=status_word(part["status"]))
                c.fill = OK_FILL if part["status"] == "submitted" else PatternFill()
            _link(ws.cell(row=r, column=7), "Open report →" if p["report"] else "", p["report"])
            r += 1
            # the programme's Curriculum and Syllabus, generated in the
            # Office's own templates, right after the programme
            for label, url in (("Curriculum (JAIN template)", p.get("curriculum_doc")),
                                ("Syllabus (JAIN template)", p.get("syllabus_doc"))):
                if not url:
                    continue
                ws.cell(row=r, column=2, value=f"   {label}").font = Font(size=9, bold=True,
                                                                         color=NAVY)
                _link(ws.cell(row=r, column=3), "Open →", url)
                r += 1
            for where, name, url in p["documents"]:
                ws.cell(row=r, column=2, value=f"   {where} document").font = Font(size=9, color="53627A")
                _link(ws.cell(row=r, column=3), name, url)
                r += 1

    _programmes_sheet(wb, rep)
    _revision_sheet(wb, rep)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# the programmes, sheet by sheet: structure, Annexure I, syllabus; revision
# ---------------------------------------------------------------------------

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
BAND = PatternFill("solid", fgColor="E8EEF6")
GREEN = PatternFill("solid", fgColor="C6E0B4")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def average_change(modules):
    """A course's revision, the mean of its modules' % change (as the form works it out)."""
    v = [_num(m.get("pct")) for m in modules or []
         if isinstance(m, dict) and str(m.get("revised") or "").strip()]
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def revision_summary(courses, threshold=20):
    """(A)–(D), as the Course Revision form shows them."""
    rows = [c for c in courses if c.get("course_code")]
    avgs = [_num(c.get("avg_change")) if _num(c.get("avg_change")) is not None
            else average_change(c.get("modules")) for c in rows]
    a = len(rows)
    b = sum(1 for x in avgs if (x or 0) > threshold)
    known = [x for x in avgs if x is not None]
    return {"A": a, "B": b, "C": round(b / a * 100, 2) if a else 0,
            "D": round(sum(known) / len(known), 2) if known else None, "avgs": avgs, "rows": rows}


def _put(ws, r, values, bold=False, fill=None, wrap=False, font=None):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=r, column=i, value=v)
        c.border = BORDER
        c.alignment = Alignment(vertical="top", wrap_text=wrap or isinstance(v, str) and len(v) > 30)
        if bold or font:
            c.font = font or Font(bold=True, size=10)
        if fill:
            c.fill = fill


def _band(ws, r, text, width, fill=BAND, color=NAVY):
    ws.cell(row=r, column=1, value=text).font = Font(bold=True, size=10, color=color)
    for col in range(1, width + 1):
        ws.cell(row=r, column=col).fill = fill
        ws.cell(row=r, column=col).border = BORDER


def _programme_list(rep):
    return rep["programmes"]["UG"] + rep["programmes"]["PG"]


def _programmes_sheet(wb, rep):
    from .report import programme_context
    ws = wb.create_sheet("Programmes")
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFGHIJK", (14, 44, 22, 6, 6, 6, 6, 9, 9, 9, 9)):
        ws.column_dimensions[col].width = w
    ws["A1"] = f"Programmes — {rep['dept'].get('dept_name', '')} · {rep['year']}"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ws["A2"] = "Each programme's structure, its minors (Annexure I) and its syllabus, as entered."
    ws["A2"].font = Font(size=10, color="53627A")
    r = 4
    db = get_db()
    for p in _programme_list(rep):
        ctx = programme_context(db, rep["dept"], rep["year"], p["programme_code"], _NoLinks())
        if not ctx:
            continue
        _section_title(ws, r, f"{p['programme_code']} — {p['programme_name']}", width=11)
        r += 1
        ws.cell(row=r, column=1, value=" · ".join(x for x in (p.get("degree_level"), p.get("specialisation"),
                                                              f"batch {p['batch']}" if p.get("batch") else "")
                                                   if x)).font = Font(italic=True, size=9, color="53627A")
        r += 2
        # structure
        ws.cell(row=r, column=1, value="Programme Structure").font = Font(bold=True, size=11, color=NAVY)
        r += 1
        if ctx["semesters"]:
            _put(ws, r, ["Course code", "Course title", "Course group", "L", "T", "P", "E", "Credits",
                         "CA marks", "TEE marks", "Total"], bold=True, fill=GREEN)
            r += 1
            total = 0
            for sem, rows in ctx["semesters"]:
                sem_cr = sum(_num(x.get("credits")) or 0 for x in rows)
                total += sem_cr
                _band(ws, r, f"Semester {sem}  ·  {sem_cr:g} credits", 11)
                r += 1
                for x in rows:
                    _put(ws, r, [x.get("course_code"), x.get("course_title"), x.get("nep_category"),
                                 x.get("l"), x.get("t"), x.get("p"), x.get("e"), x.get("credits"),
                                 x.get("cia"), x.get("ese"), x.get("total_marks")])
                    r += 1
            _put(ws, r, ["Total", "", "", "", "", "", "", total, "", "", ""], bold=True)
            r += 1
        else:
            ws.cell(row=r, column=1, value="Not entered yet.").font = Font(italic=True, color="7A8699")
            r += 1
        # Annexure I
        r += 1
        ws.cell(row=r, column=1, value="Minor / Honours — Annexure I").font = Font(bold=True, size=11, color=NAVY)
        r += 1
        if ctx["minors"]:
            _put(ws, r, ["Course code", "Course title", "Minor stream", "Sem", "", "", "", "Credits"],
                 bold=True, fill=GREEN)
            r += 1
            for m in ctx["minors"]:
                _put(ws, r, [m.get("course_code"), m.get("course_title"), m.get("minor_title"),
                             m.get("semester"), "", "", "", m.get("credits")])
                r += 1
        else:
            ws.cell(row=r, column=1, value="No minors entered.").font = Font(italic=True, color="7A8699")
            r += 1
        # syllabus
        r += 1
        ws.cell(row=r, column=1, value="Syllabus").font = Font(bold=True, size=11, color=NAVY)
        r += 1
        if ctx["syllabus"]:
            _put(ws, r, ["Course code", "Course title", "Modules (hours)", "Sem", "", "", "",
                         "Credits", "Hrs/week", "Total hrs", ""], bold=True, fill=GREEN)
            r += 1
            for c in ctx["syllabus"]:
                mods = "; ".join(f"{m.get('title') or ''} ({m.get('hours') or '—'})"
                                 for m in c.get("modules") or [] if isinstance(m, dict))
                _put(ws, r, [c.get("course_code"), c.get("course_title"), mods, c.get("semester"), "", "", "",
                             c.get("credits"), c.get("hours_per_week"), c.get("teaching_hours"), ""], wrap=True)
                r += 1
        else:
            ws.cell(row=r, column=1, value="Not entered yet.").font = Font(italic=True, color="7A8699")
            r += 1
        r += 2
    ws.freeze_panes = "A4"


def _revision_sheet(wb, rep):
    """Course Revision in the revision document's own layout: who and when,
    (A)–(D), course-wise % change by semester, then module-wise per course."""
    from .report import programme_context
    ws = wb.create_sheet("Course Revision")
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCD", (8, 60, 60, 16)):
        ws.column_dimensions[col].width = w
    ws["A1"] = f"Course Revision — {rep['dept'].get('dept_name', '')} · {rep['year']}"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    r = 3
    db = get_db()
    for p in _programme_list(rep):
        ctx = programme_context(db, rep["dept"], rep["year"], p["programme_code"], _NoLinks())
        if not ctx:
            continue
        courses = [c for c in ctx["revision"] if isinstance(c, dict)]
        _section_title(ws, r, "Percentage of change in syllabus revision for", width=4)
        r += 1
        year = next((c.get("year_latest") for c in courses if c.get("year_latest")), "")
        for label, v in (("Name of the programme", p["programme_name"]), ("Programme code", p["programme_code"]),
                         ("Name of the department", rep["dept"].get("dept_name")), ("Year of revision", year)):
            _put(ws, r, ["", label, v, ""])
            ws.cell(row=r, column=2).font = Font(bold=True, size=10)
            r += 1
        if not courses:
            ws.cell(row=r, column=2, value="No revision entered yet.").font = Font(italic=True, color="7A8699")
            r += 3
            continue
        s = revision_summary(courses)
        r += 1
        for k, label, v in (("(A)", "Total number of courses", s["A"]),
                            ("(B)", "Number of courses with syllabus revision above 20%", s["B"]),
                            ("(C)", "Percentage of courses revised — (B / A) × 100", s["C"]),
                            ("(D)", "Average percentage of syllabus revised, across all courses",
                             "—" if s["D"] is None else f"{s['D']:g}%")):
            _put(ws, r, [k, label, "", v], bold=False)
            ws.cell(row=r, column=4).font = Font(bold=True, size=10)
            r += 1
        r += 1
        ws.cell(row=r, column=1, value="Percentage of change in syllabus — course-wise, by semester").font = \
            Font(bold=True, size=11, color=NAVY)
        r += 1
        _put(ws, r, ["SL", "Course code", "Course title", "% change"], bold=True, fill=GREEN)
        r += 1
        pairs = list(zip(s["rows"], s["avgs"]))
        sems = sorted({_num(c.get("semester")) for c, _ in pairs}, key=lambda x: (x is None, x or 0))
        for sem in sems:
            _band(ws, r, f"Semester {ROMAN[int(sem) - 1] if sem and 0 < sem <= 10 else sem or '—'}", 4)
            r += 1
            for i, (c, avg) in enumerate([x for x in pairs if _num(x[0].get("semester")) == sem], 1):
                _put(ws, r, [i, c.get("course_code"), c.get("course_title"), "—" if avg is None else f"{avg:g}%"])
                r += 1
        r += 1
        ws.cell(row=r, column=1, value="Percentage of change in syllabus — module-wise for all courses").font = \
            Font(bold=True, size=11, color=NAVY)
        r += 1
        for c, avg in pairs:
            _band(ws, r, f"{c.get('course_code')} — {c.get('course_title')}", 4, fill=GREEN, color="1A1A1A")
            r += 1
            _put(ws, r, ["Module", f"Previous syllabus {c.get('year_previous') or ''}".strip(),
                         f"Revised syllabus {c.get('year_latest') or ''}".strip(), "% change"], bold=True)
            r += 1
            for n, m in enumerate([m for m in c.get("modules") or [] if isinstance(m, dict)], 1):
                pct = _num(m.get("pct"))
                _put(ws, r, [n, m.get("previous") or "—", m.get("revised") or "",
                             "—" if pct is None else f"{pct:g}%"], wrap=True)
                r += 1
            _put(ws, r, ["", "Average percentage on revision considering all modules", "",
                         "—" if avg is None else f"{avg:g}%"], bold=True)
            r += 2
        r += 1


def _word_table(doc, head, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(head))
    t.style = "Table Grid"
    for i, h in enumerate(head):
        t.rows[0].cells[i].text = h
        for r in t.rows[0].cells[i].paragraphs[0].runs:
            r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8.5)
    return t


def _word_programmes(doc, rep):
    """Each programme's structure, Annexure I and Course Revision summary."""
    from .report import programme_context
    db = get_db()
    for p in _programme_list(rep):
        ctx = programme_context(db, rep["dept"], rep["year"], p["programme_code"], _NoLinks())
        if not ctx:
            continue
        doc.add_page_break()
        doc.add_heading(f"{p['programme_code']} — {p['programme_name']}", level=1)
        doc.add_heading("Programme structure", level=2)
        rows = []
        for sem, rs in ctx["semesters"]:
            rows.append((f"Semester {sem}", "", "", f"{sum(_num(x.get('credits')) or 0 for x in rs):g}"))
            rows += [(x.get("course_code"), x.get("course_title"), x.get("nep_category"), x.get("credits"))
                     for x in rs]
        if rows:
            _word_table(doc, ("Course code", "Course title", "Course group", "Credits"), rows)
        else:
            doc.add_paragraph().add_run("Not entered yet.").italic = True
        doc.add_heading("Minor / Honours — Annexure I", level=2)
        if ctx["minors"]:
            _word_table(doc, ("Minor stream", "Sem", "Course code", "Course title", "Credits"),
                        [(m.get("minor_title"), m.get("semester"), m.get("course_code"), m.get("course_title"),
                          m.get("credits")) for m in ctx["minors"]])
        else:
            doc.add_paragraph().add_run("No minors entered.").italic = True
        doc.add_heading("Course Revision", level=2)
        courses = [c for c in ctx["revision"] if isinstance(c, dict)]
        if courses:
            s = revision_summary(courses)
            _word_table(doc, ("", "Summary", "Value"), [
                ("(A)", "Total number of courses", s["A"]),
                ("(B)", "Number of courses with syllabus revision above 20%", s["B"]),
                ("(C)", "Percentage of courses revised — (B / A) × 100", s["C"]),
                ("(D)", "Average percentage of syllabus revised", "—" if s["D"] is None else f"{s['D']:g}%")])
            doc.add_paragraph()
            _word_table(doc, ("Sem", "Course code", "Course title", "% change"),
                        [(c.get("semester"), c.get("course_code"), c.get("course_title"),
                          "—" if a is None else f"{a:g}%") for c, a in zip(s["rows"], s["avgs"])])
        else:
            doc.add_paragraph().add_run("No revision entered yet.").italic = True


class _NoLinks:
    def file(self, stage, value):
        return None

    def programme(self, code):
        return None

    def generated(self, kind, code):
        return None


# ---------------------------------------------------------------------------
# Excel — the whole institution
# ---------------------------------------------------------------------------

def institution_excel(year: str) -> io.BytesIO:
    db = get_db()
    depts = list(db.departments.find({"active": True})
                 .sort([("place", 1), ("campus", 1), ("dept_name", 1)]))
    subs = {s["dept_code"]: s for s in db.submissions.find({"academic_year": year})}

    wb = Workbook()
    ws = wb.active
    ws.title = "Status"
    ws["A1"] = f"BoS Academic Portal — institution status, {year}"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)

    header = ["Place", "Campus", "School", "Department", "Code", "Progress"] + \
             [s["title"] for s in STAGES]
    _head(ws, 3, header)
    r = 4
    for d in depts:
        sub = subs.get(d["dept_code"], {})
        p = progress(sub) if sub else {"done": 0, "total": len(STAGES)}
        row = [d.get("place"), d.get("campus"), d.get("school"), d.get("dept_name"),
               d.get("dept_code"), f"{p['done']}/{p['total']}"]
        for s in STAGES:
            row.append(compute_status(sub, s["key"]).title() if sub else "Not started")
        for i, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=i, value=_flat(v))
            c.border = BORDER
            if i > 6:
                c.fill = PatternFill("solid", fgColor={"Submitted": "DFF3E4",
                                                       "Returned": "FDE7E7",
                                                       "Draft": "FFF7E0",
                                                       "Locked": "EFEFEF"}.get(v, "FFFFFF"))
                c.alignment = Alignment(horizontal="center")
        r += 1
    ws.freeze_panes = "G4"
    _autosize(ws, max_width=28)

    # credit compliance across programmes
    cs = wb.create_sheet("Credit compliance")
    _head(cs, 1, ["Campus", "Department", "Programme", "Code", "Track", "Declared total",
                  "Required", "Shortfall", "Errors"])
    r = 2
    rules = db.rules.find_one({"_id": "ugc"}) or {}
    totals = rules.get("totals") or U.DEFAULT_TOTALS
    for d in depts:
        sub = subs.get(d["dept_code"])
        if not sub:
            continue
        progs = programmes_of(sub, d)
        for p in progs:
            pcode = p.get("programme_code")
            state = ((sub.get("programmes") or {}).get(pcode, {})
                     .get("prog_curriculum", {}))
            courses = (state.get("data") or {}).get("semester_structure") or []
            track = U.get_track(p.get("degree_level"))
            declared = sum(float(r.get("credits")) for r in courses
                           if str(r.get("credits", "")).replace(".", "", 1).isdigit())
            required = totals.get(track) if track else None
            shortfall = (required - declared) if required else ""
            errors = (state.get("summary") or {}).get("errors", "")
            for i, v in enumerate([d.get("campus"), d.get("dept_name"), p.get("programme_name"),
                                   pcode, U.TRACKS.get(track, "—"), declared or "",
                                   required or "—", shortfall if shortfall and shortfall > 0 else "",
                                   errors], start=1):
                c = cs.cell(row=r, column=i, value=_flat(v))
                c.border = BORDER
            r += 1
    _autosize(cs)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Word report
# ---------------------------------------------------------------------------

def _hyperlink(paragraph, text, url):
    """A clickable link in a Word paragraph (python-docx has no helper for it)."""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    if not url:
        return paragraph.add_run(text)
    rid = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0B4A9E")
    under = OxmlElement("w:u")
    under.set(qn("w:val"), "single")
    props.append(color)
    props.append(under)
    run.append(props)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)
    return link


def submission_word(dept_code: str, year: str, links=None) -> io.BytesIO:
    """The same single report as the Excel download, as a Word document."""
    from .report import build, status_word
    rep = build(get_db(), dept_code, year, links)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("JAIN (Deemed-to-be University) — Office of Academics")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x0F, 0x2A, 0x4A)
    sub_t = doc.add_paragraph()
    sub_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = sub_t.add_run(f"Board of Studies record · {rep['dept'].get('dept_name', dept_code)} · {year}")
    r2.font.size = Pt(11)
    r2.font.color.rgb = RGBColor(0x53, 0x62, 0x7A)

    doc.add_heading("Department information", level=1)
    t = doc.add_table(rows=0, cols=2)
    t.style = "Light Grid Accent 1"
    for k, v in rep["info"]:
        cells = t.add_row().cells
        cells[0].text = k
        cells[1].text = _flat(v)

    doc.add_heading("Stages", level=1)
    t = doc.add_table(rows=1, cols=4)
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(("Stage", "Status", "Submitted on", "Filled")):
        t.rows[0].cells[i].text = h
    for st in rep["stages"]:
        cells = t.add_row().cells
        cells[0].text = st["title"]
        cells[1].text = status_word(st["status"])
        cells[2].text = _flat(st["submitted_at"])
        cells[3].text = f"{st['filled']} of {st['total']}" + (f" {st['unit']}" if st.get("unit") else " filled")

    for st in rep["stages"]:
        if st.get("container"):
            continue
        doc.add_heading(f"{st['title']} — {status_word(st['status'])}", level=2)
        if st.get("returned_note"):
            doc.add_paragraph().add_run("Returned: " + st["returned_note"]).italic = True
        if not st["items"]:
            doc.add_paragraph().add_run("Nothing entered yet.").italic = True
        for filled, label, text, docs in st["items"]:
            para = doc.add_paragraph()
            mark = para.add_run("✓  " if filled else "✗  ")
            mark.bold = True
            mark.font.color.rgb = RGBColor(0x1F, 0x6B, 0x44) if filled else RGBColor(0xB4, 0x23, 0x18)
            para.add_run(f"{label}: ").bold = True
            if docs:
                for k, (name, url) in enumerate(docs):
                    if k:
                        para.add_run(" · ")
                    _hyperlink(para, name, url)
            else:
                para.add_run(text or "Not filled").italic = not text

    for level in ("UG", "PG"):
        progs = rep["programmes"][level]
        doc.add_heading(f"{level} programmes ({len(progs)})", level=1)
        if not progs:
            doc.add_paragraph().add_run("None.").italic = True
        for p in progs:
            para = doc.add_paragraph(style="List Bullet")
            _hyperlink(para, p["programme_name"], p["report"])
            para.add_run(f"  ({p['programme_code']}"
                         + (f", {p['degree_level']}" if p.get("degree_level") else "") + ")")
            para.add_run("\n" + " · ".join(f"{x['title']}: {status_word(x['status'])}"
                                            for x in p["parts"])).font.size = Pt(9)
            for label, url in (("Curriculum (JAIN template)", p.get("curriculum_doc")),
                                ("Syllabus (JAIN template)", p.get("syllabus_doc"))):
                if url:
                    d = doc.add_paragraph()
                    d.paragraph_format.left_indent = Pt(24)
                    d.add_run(f"{label}: ").font.size = Pt(9)
                    _hyperlink(d, "Open", url)
            for where, name, url in p["documents"]:
                d = doc.add_paragraph()
                d.paragraph_format.left_indent = Pt(24)
                d.add_run(f"{where} document: ").font.size = Pt(9)
                _hyperlink(d, name, url)

    _word_programmes(doc, rep)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Excel — one department's data mapping (Admin > Flow 3D)
# ---------------------------------------------------------------------------

def flow_mapping_excel(data: dict, per_programme: list, year: str) -> io.BytesIO:
    titles = {n["key"]: n["title"] for n in data["nodes"]}
    wb = Workbook()
    ws = wb.active
    ws.title = "Data mapping"
    d = data["department"]
    ws["A1"] = f"{d['name']} — data mapping · {year}"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ws["A2"] = "What is entered once and where the portal uses it again."
    head = ["Field", "Entered in", "Used again in", "How", "What happens", "Value"]
    _head(ws, 4, head)
    r = 5
    for f in data["flows"]:
        row = [f["field"], titles[f["from"]], ", ".join(titles[t] for t in f["to"]),
               f["how"].capitalize(), f["detail"], f["value"]]
        for i, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    ws.freeze_panes = "A5"
    _autosize(ws, max_width=60)

    ps = wb.create_sheet("By programme")
    _head(ps, 1, ["Programme code", "Programme", "Level", "Field", "Entered in",
                  "Used again in", "How", "Value"])
    r = 2
    for p, flows in per_programme:
        for f in flows:
            row = [p["code"], p["name"], p["level"], f["field"], titles[f["from"]],
                   ", ".join(titles[t] for t in f["to"]), f["how"].capitalize(), f["value"]]
            for i, v in enumerate(row, start=1):
                c = ps.cell(row=r, column=i, value=v)
                c.border = BORDER
                c.alignment = Alignment(wrap_text=True, vertical="top")
            r += 1
    ps.freeze_panes = "A2"
    _autosize(ps, max_width=50)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
