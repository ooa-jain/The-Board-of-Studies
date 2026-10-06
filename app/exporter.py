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
GOLD = "C8A44B"
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
    _head(ws, r, ["", "Stage", "Status", "Submitted on", "Filled", "", ""], fill=GOLD, color="1A1A1A")
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
                      "Report"], fill=GOLD, color="1A1A1A")
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
            for where, name, url in p["documents"]:
                ws.cell(row=r, column=2, value=f"   {where} document").font = Font(size=9, color="53627A")
                _link(ws.cell(row=r, column=3), name, url)
                r += 1

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


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
            for where, name, url in p["documents"]:
                d = doc.add_paragraph()
                d.paragraph_format.left_indent = Pt(24)
                d.add_run(f"{where} document: ").font.size = Pt(9)
                _hyperlink(d, name, url)

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
