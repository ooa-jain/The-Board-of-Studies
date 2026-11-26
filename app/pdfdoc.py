"""A programme's submitted documents as one PDF, to view.

The Curriculum, Syllabus and Course Revision are made as Word files
(docgen.py). Here the same documents — read back as blocks by docgen.to_view —
are laid out as PDF pages: a letterhead, the paragraphs and tables, a footer
with the page number. The font is the one that comes with reportlab (or
DejaVu where the server has it), so nothing is installed alongside.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache
from xml.sax.saxutils import escape

FOOT = "Prepared and Approved by Office of Academic Affairs"
NAVY = "#1F4E79"

# what a font may lack: a plain spelling, so no page shows a blank box
_PLAIN = {"→": "->", "←": "<-", "✓": "Yes", "✗": "No", "₹": "Rs.", "≤": "<=", "≥": ">=", "×": "x",
          "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "•": "-", "…": "...", " ": " "}


@lru_cache(maxsize=1)
def _fonts():
    """(regular, bold, glyphs): registered with reportlab, and the set of characters the font has."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    here = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    pairs = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             (os.path.join(here, "Vera.ttf"), os.path.join(here, "VeraBd.ttf"))]
    for reg, bold in pairs:
        if os.path.isfile(reg) and os.path.isfile(bold):
            r = TTFont("BoS-Regular", reg)
            pdfmetrics.registerFont(r)
            pdfmetrics.registerFont(TTFont("BoS-Bold", bold))
            pdfmetrics.registerFontFamily("BoS-Regular", normal="BoS-Regular", bold="BoS-Bold",
                                          italic="BoS-Regular", boldItalic="BoS-Bold")
            return "BoS-Regular", "BoS-Bold", set(r.face.charToGlyph)
    return "Helvetica", "Helvetica-Bold", set(range(32, 256))


def _clean(text) -> str:
    """The text as the font can show it, escaped for a Paragraph."""
    _, _, have = _fonts()
    out = []
    for ch in str(text or ""):
        if ord(ch) in have or ch in ("\n", " "):
            out.append(ch)
        else:
            out.append(_PLAIN.get(ch, "?" if ord(ch) > 127 else ch))
    return escape("".join(out))


def _widths(rows, width, size):
    """Column widths in points: every column wide enough for its longest word, the rest shared by how
    much text the column holds."""
    n = max((sum(c["span"] for c in r) for r in rows), default=1)
    longest, word = [0] * n, [0] * n
    for r in rows:
        at = 0
        for c in r:
            if c["span"] == 1:
                for l in c["lines"]:
                    t = l["text"]
                    longest[at] = max(longest[at], min(len(t), 40))
                    word[at] = max([word[at]] + [len(w) for w in t.split()])
            at += c["span"]
    pt = size * 0.56
    least = [max(word[k], 3) * pt + 8 for k in range(n)]
    want = [max(longest[k], 3) * pt + 8 for k in range(n)]
    if sum(want) <= width:
        scale = width / sum(want)
        return n, [w * scale for w in want]
    room = max(width - sum(least), 0)
    extra = [w - l for w, l in zip(want, least)]
    total = sum(extra) or 1
    out = [l + room * e / total for l, e in zip(least, extra)]
    scale = width / sum(out)
    return n, [w * scale for w in out]


def views_pdf(title, views, logo=None) -> bytes:
    """`views`: [(heading, view)] with each view from docgen.to_view. Returns the PDF."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
                                    Paragraph, Spacer, Table, TableStyle)

    regular, bold, _ = _fonts()
    buf = io.BytesIO()
    pages = {"portrait": A4, "landscape": landscape(A4)}
    state = {"head": views[0][1].get("header") if views else title}

    def draw(canvas, doc):
        w, h = canvas._pagesize                 # this page's own size (portrait or landscape)
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        from reportlab.pdfbase.pdfmetrics import stringWidth
        head = _clean(state["head"]).replace("&amp;", "&")
        room = w - 28 * mm - 32 * mm                      # clear of the logo on the right
        while head and stringWidth(head, regular, 8) > room:
            head = head[:-2]
        canvas.drawString(14 * mm, h - 12 * mm, head)
        if logo and os.path.isfile(logo):
            try:
                canvas.drawImage(logo, w - 14 * mm - 26 * mm, h - 16 * mm, width=26 * mm, height=7.5 * mm,
                                 mask="auto", preserveAspectRatio=True)
            except Exception:
                pass
        canvas.setStrokeColor(colors.HexColor("#C0504D"))
        canvas.setLineWidth(1.2)
        canvas.line(14 * mm, h - 18 * mm, w - 14 * mm, h - 18 * mm)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(14 * mm, 9 * mm, FOOT)
        canvas.drawRightString(w - 14 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, title=title, author="Office of Academic Affairs",
                          leftMargin=14 * mm, rightMargin=14 * mm, topMargin=22 * mm, bottomMargin=16 * mm)
    first_kind = "landscape" if views and views[0][1].get("landscape") else "portrait"
    for name in sorted(pages, key=lambda k: k != first_kind):
        size = pages[name]
        frame = Frame(14 * mm, 14 * mm, size[0] - 28 * mm, size[1] - 36 * mm, id=name, leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate(id=name, frames=[frame], onPage=draw, pagesize=size)])

    align = {"center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}
    flow, first = [], True
    for heading, view in views:
        kind = "landscape" if view.get("landscape") else "portrait"
        width = pages[kind][0] - 28 * mm
        if first:
            first = False
        else:
            flow.append(NextPageTemplate(kind))
            flow.append(PageBreak())
        for k, v in view["blocks"]:
            if k == "break":
                flow.append(PageBreak())
            elif k == "p":
                st = ParagraphStyle("p", fontName=bold if v["bold"] else regular, fontSize=min(max(v["size"], 8), 18),
                                    leading=min(max(v["size"], 8), 18) * 1.25, alignment=align.get(v["align"], TA_LEFT),
                                    textColor=colors.HexColor("#" + v["color"]) if v.get("color") else colors.black,
                                    spaceAfter=3)
                flow.append(Paragraph(_clean(v["text"]), st))
            else:
                t = _table(v, width, regular, bold, colors, ParagraphStyle, Paragraph, Table, TableStyle, align)
                if t is not None:
                    flow.append(t)
                    flow.append(Spacer(1, 6))

    doc.build(flow or [Paragraph("Nothing is submitted yet.", ParagraphStyle("e", fontName=regular))])
    return buf.getvalue()


def _table(rows, width, regular, bold, colors, ParagraphStyle, Paragraph, Table, TableStyle, align):
    rows = [r for r in rows if r]
    if not rows:
        return None
    n = max((sum(c["span"] for c in r) for r in rows), default=1)
    size = 8.5 if n <= 8 else 7.5 if n <= 12 else 6.8
    n, widths = _widths(rows, width, size)
    data, style = [], [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
                       ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                       ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    for ri, row in enumerate(rows):
        cells, col = [], 0
        for c in row:
            parts = []
            for l in c["lines"]:
                st = ParagraphStyle("c", fontName=bold if l["bold"] else regular, fontSize=size, leading=size * 1.22,
                                    alignment=align.get(l["align"], 0),
                                    textColor=colors.HexColor("#" + l["color"]) if l.get("color") else colors.black)
                parts.append(Paragraph(_clean(l["text"]) or "&nbsp;", st))
            cells.append(parts or "")
            if c["span"] > 1:
                style.append(("SPAN", (col, ri), (col + c["span"] - 1, ri)))
            if c.get("fill"):
                style.append(("BACKGROUND", (col, ri), (col + c["span"] - 1, ri), colors.HexColor("#" + c["fill"])))
            cells.extend([""] * (c["span"] - 1))
            col += c["span"]
        cells.extend([""] * (n - len(cells)))
        data.append(cells)
    # a title or heading row (shaded) repeats on the next page; a table that starts with data does not
    head = 1 if len(rows) > 1 and all(c.get("fill") for c in rows[0]) else 0
    t = Table(data, colWidths=widths, repeatRows=head)
    t.setStyle(TableStyle(style))
    return t
