"""The BoS portal orientation deck (8 slides), as a PowerPoint file.

Light theme, the portal's real screenshots, entrance animations on every
slide, fade transitions, and a clickable menu on every slide (each slide's
number jumps to it; Back / Next at the foot).

    python3 tools/make_orientation_deck.py <screenshots folder> <out.pptx>
"""
import copy
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "screenshots"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "BoS-Portal-Orientation.pptx"
LOGO = ROOT / "app" / "static" / "img" / "jain-logo.png"

NAVY = RGBColor(0x0E, 0x2A, 0x5C)
BLUE = RGBColor(0x25, 0x63, 0xEB)
SKY = RGBColor(0xE8, 0xF0, 0xFE)
BG = RGBColor(0xF7, 0xFA, 0xFF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x55, 0x65, 0x7E)
LINE = RGBColor(0xD6, 0xE0, 0xF0)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
GREEN_BG = RGBColor(0xEA, 0xF7, 0xEF)
RED = RGBColor(0xDC, 0x26, 0x26)
RED_BG = RGBColor(0xFD, 0xEE, 0xEE)
AMBER_BG = RGBColor(0xFF, 0xF7, 0xE6)
FONT = "Calibri"

NAV = ["Objective", "Why", "Scope", "Portal", "Workflow", "Roles", "Timelines", "Next steps"]

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
slides = []
anim = {}          # slide -> [shapes, in the order they come in]


# ------------------------------------------------------------------ helpers

def box(slide, x, y, w, h, fill=WHITE, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.shadow.inherit = False
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.text_frame.text = ""
    return s


def text(slide, x, y, w, h, runs, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.1, shape=None):
    """runs: a string, or a list of paragraphs; a paragraph is a string or
    a list of (text, {size,color,bold}) pieces."""
    if shape is None:
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        pieces = para if isinstance(para, list) else [(para, {})]
        for t, st in pieces:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(st.get("size", size))
            f.bold = st.get("bold", bold)
            f.color.rgb = st.get("color", color)
    return shape


def picture(slide, path, x, y, w=None, h=None, crop=None, border=True):
    """A picture at x, y, w wide; with crop=(left, top, right, bottom), the
    height follows what is left, so nothing is squeezed."""
    from PIL import Image
    iw, ih = Image.open(path).size
    cl, ct, cr, cb = crop or (0, 0, 0, 0)
    if w and not h:
        h = w * (ih * (1 - ct - cb)) / (iw * (1 - cl - cr))
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    if crop:
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = crop
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(1)
        # a soft shadow under the screenshot
        sp = pic._element.spPr
        eff = etree.SubElement(sp, qn("a:effectLst"))
        sh = etree.SubElement(eff, qn("a:outerShdw"), blurRad="190500", dist="38100", dir="5400000",
                              algn="t", rotWithShape="0")
        c = etree.SubElement(sh, qn("a:srgbClr"), val="0E2A5C")
        etree.SubElement(c, qn("a:alpha"), val="22000")
    return pic


def badge(slide, x, y, d, label, fill=BLUE, color=WHITE, size=16):
    s = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    text(slide, 0, 0, 0, 0, label, size=size, color=color, bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, shape=s)
    s.text_frame.margin_left = s.text_frame.margin_right = 0
    return s


def link(shape, target):
    shape.click_action.target_slide = target


def new_slide(n, title, kicker):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    slides.append(s)
    anim[id(s)] = []
    # the top band: logo, and the slide menu (filled in once every slide exists)
    s.shapes.add_picture(str(LOGO), Inches(0.45), Inches(0.28), height=Inches(0.42))
    k = text(s, 0.5, 0.95, 8, 0.35, kicker.upper(), size=12, color=BLUE, bold=True)
    t = text(s, 0.5, 1.22, 8.8, 0.8, title, size=34, color=NAVY, bold=True)
    bar = box(s, 0.55, 1.98, 1.1, 0.07, fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
    anim[id(s)] += [k, t, bar]
    return s


def add_nav():
    """Every slide: 1–8 to jump to any slide (this one marked), Back / Next."""
    for i, s in enumerate(slides):
        x = 4.55
        for j, name in enumerate(NAV):
            w = 0.36 + 0.075 * len(name)
            on = i == j
            p = box(s, x, 0.33, w, 0.34, fill=BLUE if on else WHITE, line=None if on else LINE, radius=0.5)
            text(s, 0, 0, 0, 0, [[(f"{j + 1} ", {"bold": True}), (name, {})]], size=10,
                 color=WHITE if on else NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=p)
            p.text_frame.margin_left = p.text_frame.margin_right = 0
            if not on:
                link(p, slides[j])
            x += w + 0.06
        # the foot: slide number, Back, Next
        text(s, 0.5, 7.02, 6, 0.3, f"BoS Data Submission Portal · AY 2027–28  ·  {i + 1} / {len(slides)}",
             size=10, color=MUTED)
        if i > 0:
            b = box(s, 10.9, 6.95, 1.0, 0.36, fill=WHITE, line=LINE, radius=0.5)
            text(s, 0, 0, 0, 0, "‹ Back", size=11, color=NAVY, bold=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE, shape=b)
            link(b, slides[i - 1])
        if i < len(slides) - 1:
            nx = box(s, 12.0, 6.95, 0.95, 0.36, fill=BLUE, radius=0.5)
            text(s, 0, 0, 0, 0, "Next ›", size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE, shape=nx)
            link(nx, slides[i + 1])


# ---------------------------------------------------------- animations (XML)

P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _effect(ids, spid, delay, first, rise):
    """One entrance: fade in (and rise a little), starting `delay` ms after
    the slide opens."""
    nid = lambda: str(next(ids))
    par = etree.Element(qn("p:par"))
    ctn = etree.SubElement(par, qn("p:cTn"), id=nid(), fill="hold")
    st = etree.SubElement(ctn, qn("p:stCondLst"))
    etree.SubElement(st, qn("p:cond"), delay=str(delay))
    kids = etree.SubElement(ctn, qn("p:childTnLst"))
    par2 = etree.SubElement(kids, qn("p:par"))
    c2 = etree.SubElement(par2, qn("p:cTn"), id=nid(), presetID="10", presetClass="entr",
                          presetSubtype="0", fill="hold",
                          nodeType="afterEffect" if first else "withEffect")
    st2 = etree.SubElement(c2, qn("p:stCondLst"))
    etree.SubElement(st2, qn("p:cond"), delay="0")
    k2 = etree.SubElement(c2, qn("p:childTnLst"))
    # visible
    s = etree.SubElement(k2, qn("p:set"))
    b = etree.SubElement(s, qn("p:cBhvr"))
    c3 = etree.SubElement(b, qn("p:cTn"), id=nid(), dur="1", fill="hold")
    etree.SubElement(etree.SubElement(c3, qn("p:stCondLst")), qn("p:cond"), delay="0")
    etree.SubElement(etree.SubElement(b, qn("p:tgtEl")), qn("p:spTgt"), spid=str(spid))
    etree.SubElement(etree.SubElement(b, qn("p:attrNameLst")), qn("p:attrName")).text = "style.visibility"
    etree.SubElement(etree.SubElement(s, qn("p:to")), qn("p:strVal"), val="visible")
    # fade
    ae = etree.SubElement(k2, qn("p:animEffect"), transition="in", filter="fade")
    b = etree.SubElement(ae, qn("p:cBhvr"))
    etree.SubElement(b, qn("p:cTn"), id=nid(), dur="500")
    etree.SubElement(etree.SubElement(b, qn("p:tgtEl")), qn("p:spTgt"), spid=str(spid))
    if rise:
        a = etree.SubElement(k2, qn("p:anim"), calcmode="lin", valueType="num")
        b = etree.SubElement(a, qn("p:cBhvr"), additive="base")
        etree.SubElement(b, qn("p:cTn"), id=nid(), dur="500", fill="hold")
        etree.SubElement(etree.SubElement(b, qn("p:tgtEl")), qn("p:spTgt"), spid=str(spid))
        etree.SubElement(etree.SubElement(b, qn("p:attrNameLst")), qn("p:attrName")).text = "ppt_y"
        tl = etree.SubElement(a, qn("p:tavLst"))
        for tm, v in (("0", "#ppt_y+0.04"), ("100000", "#ppt_y")):
            tav = etree.SubElement(tl, qn("p:tav"), tm=tm)
            etree.SubElement(etree.SubElement(tav, qn("p:val")), qn("p:strVal"), val=v)
    return par


def add_animations(slide, shapes, step=220):
    """The slide's shapes come in one after another as the slide opens —
    no clicks needed — and the slide itself fades in."""
    sld = slide._element
    # the fade between slides
    tr = etree.Element(qn("p:transition"), spd="med")
    etree.SubElement(tr, qn("p:fade"))
    timing = etree.Element(qn("p:timing"))
    ids = iter(range(1, 100000))
    nid = lambda: str(next(ids))
    tn = etree.SubElement(etree.SubElement(timing, qn("p:tnLst")), qn("p:par"))
    root = etree.SubElement(tn, qn("p:cTn"), id=nid(), dur="indefinite", restart="never", nodeType="tmRoot")
    rk = etree.SubElement(root, qn("p:childTnLst"))
    seq = etree.SubElement(rk, qn("p:seq"), concurrent="1", nextAc="seek")
    main = etree.SubElement(seq, qn("p:cTn"), id=nid(), dur="indefinite", nodeType="mainSeq")
    mk = etree.SubElement(main, qn("p:childTnLst"))
    grp = etree.SubElement(mk, qn("p:par"))
    gc = etree.SubElement(grp, qn("p:cTn"), id=nid(), fill="hold")
    gst = etree.SubElement(gc, qn("p:stCondLst"))
    etree.SubElement(gst, qn("p:cond"), delay="indefinite")
    c = etree.SubElement(gst, qn("p:cond"), evt="onBegin", delay="0")
    etree.SubElement(c, qn("p:tn"), val="2")
    gk = etree.SubElement(gc, qn("p:childTnLst"))
    for n, sh in enumerate(shapes):
        rise = n >= 3   # the kicker, title and bar fade; the rest rise in too
        gk.append(_effect(ids, sh.shape_id, n * step, n == 0, rise))
    for tag in ("p:prevCondLst", "p:nextCondLst"):
        cl = etree.SubElement(seq, qn(tag))
        cd = etree.SubElement(cl, qn("p:cond"), evt="onPrev" if "prev" in tag else "onNext", delay="0")
        etree.SubElement(etree.SubElement(cd, qn("p:tgtEl")), qn("p:sldTgt"))
    # order inside <p:sld>: cSld, clrMapOvr, transition, timing
    after = sld.find(qn("p:clrMapOvr"))
    if after is None:
        after = sld.find(qn("p:cSld"))
    after.addnext(tr)
    tr.addnext(timing)


shot = lambda n: SHOTS / n

# ------------------------------------------------------------------- slide 1
s = prs.slides.add_slide(BLANK)
s.background.fill.solid()
s.background.fill.fore_color.rgb = BG
slides.append(s)
anim[id(s)] = []
# the campus photo, cut to a 5.6 x 5.85 in frame from the middle of the picture
camp = picture(s, shot("00-campus.jpg"), 7.25, 0.95, w=5.6, crop=(0.23, 0.0, 0.23, 0.0))
s.shapes.add_picture(str(LOGO), Inches(0.6), Inches(0.5), height=Inches(0.6))
k = text(s, 0.6, 1.45, 6.3, 0.35, "OFFICE OF ACADEMIC AFFAIRS · JAIN (DEEMED-TO-BE UNIVERSITY)", size=12,
         color=BLUE, bold=True)
t = text(s, 0.6, 1.8, 6.4, 1.5, "BoS Data Submission Portal", size=44, color=NAVY, bold=True, spacing=0.95)
ay = box(s, 0.62, 3.35, 2.6, 0.5, fill=BLUE, radius=0.5)
text(s, 0, 0, 0, 0, "Academic Year 2027–28", size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER,
     anchor=MSO_ANCHOR.MIDDLE, shape=ay)
card = box(s, 0.6, 4.15, 6.1, 2.55, fill=WHITE, line=LINE)
text(s, 0.85, 4.3, 5.6, 0.4, "MEETING OBJECTIVE", size=12, color=BLUE, bold=True)
objs = ["Introduce the portal every department will use for its BoS record",
        "Walk through what to submit, how, and by when",
        "Agree on the next steps for each department"]
o = text(s, 0.85, 4.7, 5.7, 1.9, [[("✓  ", {"color": GREEN, "bold": True}), (x, {})] for x in objs],
         size=17, color=INK, spacing=1.35)
anim[id(s)] += [k, t, ay, card, o]

# ------------------------------------------------------------------- slide 2
s = new_slide(2, "Why a Centralised Portal?", "Purpose and expected outcomes")
before = box(s, 0.5, 2.35, 5.4, 2.6, fill=RED_BG)
text(s, 0.75, 2.5, 5, 0.4, "UNTIL NOW", size=12, color=RED, bold=True)
bt = text(s, 0.75, 2.9, 5, 2, [[("✕  ", {"color": RED, "bold": True}), (x, {})] for x in
                               ["Records travelled by e-mail, files and folders",
                                "Different formats from every department",
                                "Hard to check, easy to lose",
                                "Progress known only by follow-up calls"]], size=16, spacing=1.35)
arrow = box(s, 6.05, 3.35, 0.9, 0.6, fill=BLUE, shape=MSO_SHAPE.RIGHT_ARROW)
after = box(s, 7.1, 2.35, 5.75, 2.6, fill=GREEN_BG)
text(s, 7.35, 2.5, 5, 0.4, "WITH THE PORTAL", size=12, color=GREEN, bold=True)
at = text(s, 7.35, 2.9, 5.4, 2, [[("✓  ", {"color": GREEN, "bold": True}), (x, {})] for x in
                                 ["One place and one format for every department",
                                  "Checked as you go: credits, UGC rules, documents",
                                  "Saved as you type, with version history",
                                  "Live progress for the Office of Academic Affairs"]], size=16, spacing=1.35)
tiles = []
for i, (h, d) in enumerate([("Complete", "every stage filled and checked before it is submitted"),
                            ("On time", "deadlines met, with fewer follow-ups"),
                            ("Accreditation-ready", "one approved record for approvals and audits")]):
    x = 0.5 + i * 4.18
    tl = box(s, x, 5.2, 4.0, 1.5, fill=WHITE, line=LINE)
    text(s, 0, 0, 0, 0, [[(h, {"size": 20, "bold": True, "color": NAVY})], [(d, {"size": 14, "color": MUTED})]],
         shape=tl, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    tiles.append(tl)
anim[id(s)] += [before, bt, arrow, after, at] + tiles

# ------------------------------------------------------------------- slide 3
s = new_slide(3, "Scope of BoS Documentation", "Document categories and information required")
cats = [("1", "Department Information", "Faculty and student numbers; the programmes you run"),
        ("2", "Pre-BoS", "Signed DIAC and DPAC compositions; Pre-BoS minutes"),
        ("3", "BoS Documents", "Meeting date, composition, minutes, attendance, photos, expert profiles, feedback"),
        ("4", "Curriculum", "Programme structure, syllabus and course revision — for every programme")]
cards = []
for i, (n, h, d) in enumerate(cats):
    y = 2.35 + i * 1.12
    c = box(s, 0.5, y, 5.3, 1.0, fill=WHITE, line=LINE)
    badge(s, 0.68, y + 0.22, 0.56, n)
    text(s, 1.42, y + 0.1, 4.3, 0.85, [[(h, {"size": 17, "bold": True, "color": NAVY})],
                                       [(d, {"size": 12.5, "color": MUTED})]], spacing=1.05)
    cards.append(c)
pic = picture(s, shot("05-pre-bos-uploads.png"), 6.15, 2.35, w=6.7)
cap = text(s, 6.15, 6.2, 6.7, 0.5, [[("Real screen · ", {"bold": True, "color": BLUE}),
                                     ("each upload is read and checked the moment it arrives", {})]],
           size=13, color=MUTED)
anim[id(s)] += cards + [pic, cap]

# ------------------------------------------------------------------- slide 4
s = new_slide(4, "Portal Architecture & Dashboard", "Main screens and navigation")
pw, px, py = 8.1, 4.75, 2.25
pic = picture(s, shot("03-department-home.png"), px, py, w=pw)
ph = pw * 1080 / 1920
marks = [("1", 0.06, 0.30, "Left menu", "Home, Progress, Reports, the four stages, Help, Query, Report a bug, Language"),
         ("2", 0.42, 0.27, "Next step", "Always shows what to do next, with one button to go there"),
         ("3", 0.42, 0.37, "Progress", "How many stages are complete"),
         ("4", 0.42, 0.47, "Your programmes", "Each programme's parts and where they stand")]
legend, pins = [], []
for i, (n, fx, fy, h, d) in enumerate(marks):
    pins.append(badge(s, px + fx * pw - 0.2, py + fy * ph - 0.2, 0.4, n, size=13))
    y = 2.3 + i * 1.08
    legend.append(text(s, 0.5, y, 4.05, 1.0, [[(f"{n}  ", {"bold": True, "color": BLUE, "size": 17}),
                                               (h, {"bold": True, "color": NAVY, "size": 17})],
                                              [(d, {"size": 13, "color": MUTED})]], spacing=1.05))
note = box(s, 0.5, 6.35, 4.05, 0.5, fill=SKY, radius=0.3)
text(s, 0, 0, 0, 0, "Saves as you type · English, हिन्दी, ಕನ್ನಡ, தமிழ், മലയാളം", size=12, color=NAVY,
     bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=note)
anim[id(s)] += [pic] + pins + legend + [note]

# ------------------------------------------------------------------- slide 5
s = new_slide(5, "Submission Workflow", "Step by step")
steps = [("Sign in", "Department login; who is working; terms"),
         ("Department Information", "Faculty, students, programmes"),
         ("Pre-BoS", "Signed DIAC, DPAC, minutes"),
         ("BoS Documents", "Minutes, attendance, photos"),
         ("Curriculum", "Structure, syllabus, revision"),
         ("Approve & submit", "HoD, then Dean; submit all")]
chev = []
w = 2.12
for i, (h, d) in enumerate(steps):
    x = 0.45 + i * (w + 0.02)
    shp = MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON
    c = box(s, x, 2.3, w, 0.85, fill=BLUE if i == len(steps) - 1 else NAVY, shape=shp)
    text(s, 0, 0, 0, 0, [[(f"{i + 1}  ", {"bold": True, "color": RGBColor(0x9D, 0xC2, 0xFF)}), (h, {"bold": True})]],
         size=13, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=c)
    dd = text(s, x + 0.1, 3.2, w - 0.2, 0.6, d, size=11.5, color=MUTED, align=PP_ALIGN.CENTER)
    chev += [c, dd]
pic = picture(s, shot("10-review-and-approval.png"), 0.5, 3.95, w=3.6, crop=(0.2, 0.05, 0.2, 0.1))
side = box(s, 4.4, 3.95, 8.45, 2.85, fill=WHITE, line=LINE)
text(s, 4.65, 4.05, 8.0, 0.75, [[("REAL SCREEN · REVIEW & SUBMIT", {"bold": True, "color": BLUE, "size": 12})],
                                [("Before the final submit", {"bold": True, "color": NAVY, "size": 18})]], spacing=1.1)
checks = ["Every page is checked as you fill it", "The Head of the Department approves, then the Dean",
          "Their approval is printed in the documents", "Every stage is submitted in one step",
          "The Office can return a stage for correction", "Version history keeps every change"]
lft = text(s, 4.65, 4.9, 3.95, 1.8, [[("✓  ", {"color": GREEN, "bold": True}), (c, {})] for c in checks[:3]],
           size=13.5, spacing=1.3)
rgt = text(s, 8.65, 4.9, 4.1, 1.8, [[("✓  ", {"color": GREEN, "bold": True}), (c, {})] for c in checks[3:]],
           size=13.5, spacing=1.3)
anim[id(s)] += chev + [pic, side, lft, rgt]

# ------------------------------------------------------------------- slide 6
s = new_slide(6, "Roles & Responsibilities", "Directors, HoDs, SPOCs and the Office of Academic Affairs")
roles = [("SPOC", "Single Point of Contact", ["Fills the record, stage by stage", "Uploads the signed documents",
                                               "Raises queries and reports bugs"]),
         ("HoD", "Head of the Department", ["Checks the content", "Approves the record before submission",
                                            "Nominates the SPOC"]),
         ("Director / Dean", "of the School", ["Gives the final approval", "Ensures every department in the school is on time"]),
         ("OoA", "Office of Academic Affairs", ["Reviews each submission", "Sends back what needs correction",
                                                "Supports every department"])]
rc = []
for i, (h, sub, pts) in enumerate(roles):
    x = 0.5 + i * 3.13
    c = box(s, x, 2.35, 2.95, 4.35, fill=WHITE, line=LINE)
    top = box(s, x, 2.35, 2.95, 0.16, fill=BLUE if i != 3 else GREEN, shape=MSO_SHAPE.RECTANGLE)
    badge(s, x + 0.25, 2.75, 0.7, h[0], fill=SKY, color=BLUE, size=22)
    text(s, x + 0.25, 3.55, 2.5, 0.9, [[(h, {"bold": True, "size": 20, "color": NAVY})],
                                      [(sub, {"size": 12, "color": MUTED})]], spacing=1.0)
    text(s, x + 0.25, 4.5, 2.55, 2.1, [[("•  ", {"color": BLUE, "bold": True}), (p, {})] for p in pts],
         size=13.5, spacing=1.3)
    rc.append(c)
anim[id(s)] += rc

# ------------------------------------------------------------------- slide 7
s = new_slide(7, "Important Timelines & Guidelines", "UG / PG deadlines and submission requirements")
line = box(s, 1.2, 3.15, 10.9, 0.08, fill=LINE, shape=MSO_SHAPE.RECTANGLE)
ms = []
for i, (h, sub) in enumerate([("Pre-BoS", "DIAC, DPAC, minutes"), ("BoS meeting", "and its documents"),
                              ("UG submission", "all UG programmes"), ("PG submission", "all PG programmes")]):
    x = 2.0 + i * 3.11
    dot = badge(s, x - 0.22, 2.97, 0.44, str(i + 1), size=13)
    c = box(s, x - 1.35, 3.55, 2.7, 1.25, fill=WHITE, line=LINE)
    text(s, 0, 0, 0, 0, [[(h, {"bold": True, "size": 17, "color": NAVY})], [(sub, {"size": 12, "color": MUTED})],
                         [("[date]", {"bold": True, "size": 16, "color": BLUE})]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=c)
    ms += [dot, c]
g = box(s, 0.5, 5.05, 12.35, 1.75, fill=AMBER_BG)
rules = ["Signed, final documents only", "Course codes and credits exactly as approved",
         "One login per department; each person's name is recorded", "Keep your own backup of every file",
         "Submitted means locked — only the Office can send it back", "Use Help, Query or Report a bug when stuck"]
gl = text(s, 0.8, 5.15, 5.9, 1.6, [[("✓  ", {"color": GREEN, "bold": True}), (r, {})] for r in rules[:3]], size=14.5,
          spacing=1.35)
gr = text(s, 6.9, 5.15, 5.9, 1.6, [[("✓  ", {"color": GREEN, "bold": True}), (r, {})] for r in rules[3:]], size=14.5,
          spacing=1.35)
anim[id(s)] += [line] + ms + [g, gl, gr]

# ------------------------------------------------------------------- slide 8
s = new_slide(8, "Next Steps & Action Points", "Departmental readiness and support")
acts = ["Nominate your SPOC", "Sign in and check your department's details",
        "Gather the signed DIAC, DPAC and BoS documents", "Begin with Department Information"]
ac = []
for i, a in enumerate(acts):
    y = 2.35 + i * 0.95
    c = box(s, 0.5, y, 5.9, 0.8, fill=WHITE, line=LINE)
    badge(s, 0.68, y + 0.16, 0.48, str(i + 1), size=14)
    text(s, 1.35, y + 0.1, 4.9, 0.6, a, size=16.5, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    ac.append(c)
sup = box(s, 6.75, 2.35, 6.1, 1.55, fill=SKY)
text(s, 7.0, 2.45, 5.7, 1.4, [[("SUPPORT, ONE CLICK AWAY", {"bold": True, "color": BLUE, "size": 12})],
                              [("▶  Help video and user manual", {})],
                              [("?  Query — opens the video where it shows how", {})],
                              [("⚑  Report a bug, with a screenshot", {})]], size=14.5, color=NAVY, spacing=1.25)
pic = picture(s, shot("12-office-dashboard.png"), 7.2, 4.1, w=5.2, crop=(0.0, 0.0, 0.0, 0.12))
thanks = text(s, 0.5, 6.25, 5.9, 0.5, [[("Thank you", {"bold": True, "size": 22, "color": NAVY}),
                                        ("  · Office of Academic Affairs", {"size": 14, "color": MUTED})]])
anim[id(s)] += ac + [sup, pic, thanks]

# ------------------------------------------------------------ finish: menu, animations
add_nav()
for s in slides:
    add_animations(s, anim[id(s)])
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print("saved", OUT)
