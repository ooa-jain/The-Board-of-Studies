#!/usr/bin/env python3
"""
The department's Help, made from the portal itself: a walkthrough video,
section by section, and the user manual (PDF).

    python tools/help_media.py              # captions, no voice
    python tools/help_media.py --voice      # with a spoken voice (edge-tts;
                                            # needs speech.platform.bing.com)
    python tools/help_media.py --only 3     # one section, to try a change

It runs the portal with an in-memory database (tools/devserver.py), makes the
demo department, fills it with sample data and records each section with
Playwright — a pointer to follow, a ring round what is clicked, a caption for
what is said and a title card per section. Out come, in app/static/help/:

    walkthrough.mp4   the sections in one video, with chapter marks
    chapters.json     each section's title and start (the Help page lists them)
    captions.vtt      what is said, as subtitles
    poster.jpg        the video's first picture
    manual.pdf        the user manual, with pictures taken along the way

Needs Playwright with Chromium and ffmpeg (both on a developer's machine, not
the server); --voice also needs `pip install edge-tts`.
"""

import argparse
import glob
import hashlib
import html
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "help"
WORK = Path(os.environ.get("HELP_WORK") or ROOT / "uploads" / "_help_work")
VIEW = {"width": 1280, "height": 720}
PORT = int(os.environ.get("HELP_PORT") or 5399)
B = f"http://127.0.0.1:{PORT}"
VOICE = "en-IN-NeerjaNeural"          # a clear Indian-English voice

# ---------------------------------------------------------------------------
# what is said, section by section (the manual's words are further down)
# ---------------------------------------------------------------------------

SECTIONS = [
    {"key": "start", "title": "Signing in and your home page", "sub": "Sign in, say who you are, find your way"},
    {"key": "dept", "title": "Department Information", "sub": "Stage 1 · the programmes you run"},
    {"key": "prebos", "title": "Pre-BoS", "sub": "Stage 2 · signed DIAC, DPAC and minutes"},
    {"key": "bosdocs", "title": "BoS Documents", "sub": "Stage 3 · the meeting and its documents"},
    {"key": "curriculum", "title": "Curriculum", "sub": "Stage 4 · a programme's Curriculum"},
    {"key": "syllabus", "title": "Syllabus", "sub": "One sheet per course"},
    {"key": "revision", "title": "Course Revision", "sub": "Previous and revised syllabus"},
    {"key": "earlier", "title": "Earlier batches", "sub": "The same three parts for each earlier batch"},
    {"key": "submit", "title": "Checking and submitting", "sub": "Autosave, the checks, Submit"},
    {"key": "reports", "title": "Reports", "sub": "See your submission"},
    {"key": "more", "title": "Version history, password and help", "sub": ""},
]

SAY = {
    "start.intro": "Welcome to the Board of Studies portal of JAIN University. This walkthrough shows how a department "
                   "fills its record, stage by stage.",
    "start.signin": "Open the portal and sign in with the username and password the Office of Academic Affairs "
                    "issued to your department.",
    "start.who": "The first time on a computer, the portal asks who you are. Your name and e-mail go with every "
                 "change you save, so the Office knows who did what.",
    "start.home": "Your home page shows the next step, with one button to continue where you left off.",
    "start.progress": "Below it, how many stages are done, and your submissions, programme by programme.",
    "start.side": "The menu on the left takes you to every stage: Department Information, Pre-BoS, BoS Documents "
                  "and Curriculum. A blue dot means in progress; green means submitted.",

    "dept.open": "Stage one is Department Information. Your department's name, faculty, school and campus come "
                 "from the Office's records.",
    "dept.progs": "Below, tick the programmes you run this year: UG on the left, PG on the right.",
    "dept.add": "A programme missing from the list? Add it here. Remove takes off one you do not run.",
    "dept.save": "There is no save button. Every change saves itself, and the bar at the end of the page says so.",

    "prebos.open": "Stage two, Pre-BoS, collects the signed DIAC and DPAC compositions and the minutes of the "
                   "Pre-BoS meeting.",
    "prebos.template": "Download the template, fill it in, sign it, and upload it: as a Word file, or as a signed "
                       "PDF or scanned copy.",
    "prebos.upload": "Drag a file onto the box, or press Choose file.",
    "prebos.check": "Each upload is read straight away. A Word form is checked row by row, and the keywords show "
                    "whether it is the right document. It is only a guide: a scanned copy is fine to submit.",
    "prebos.card": "Open or View shows the file. Remove takes it away, so you can upload another.",

    "bosdocs.open": "Stage three, BoS Documents: the date of the Board of Studies meeting, and its documents.",
    "bosdocs.list": "The composition of BoS members, profiles of the external experts, the minutes, geotagged "
                    "photos, the attendance sheet, the vision and mission, and the stakeholder feedback, each in "
                    "its own box.",
    "bosdocs.req": "A red star marks a document you must upload. The others are optional.",

    "curriculum.list": "Stage four is the Curriculum, programme by programme. Choose UG or PG, then open a programme.",
    "curriculum.parts": "Each programme has three parts: Curriculum, Syllabus and Course Revision, for the current "
                        "batch, and the same for each earlier batch.",
    "curriculum.details": "Programme details come first. For a UG programme, the degree is worked out from its "
                          "programme structure.",
    "curriculum.objective": "Write the programme's objectives, one per line.",
    "curriculum.pos": "Then its Programme Outcomes and Programme Specific Outcomes. Add the next one with the "
                      "button. Every course's CO-PO mapping takes these columns.",
    "curriculum.regs": "The regulations follow. Where a box shows grey sample wording, leaving it empty accepts "
                       "that wording.",
    "curriculum.structure": "The programme structure lists every course, semester by semester, with its category, "
                            "L-T-P-E hours, credits and marks.",
    "curriculum.credits": "The credit tables fill themselves from the structure, and the UGC Table 2 strip at the "
                          "top tells you whether the credits meet the requirement.",

    "syllabus.open": "The Syllabus has one sheet per course. Pick a semester and a course. Its information comes "
                     "straight from the Curriculum.",
    "syllabus.objectives": "The course objectives start from the programme's objectives. Change them for the course.",
    "syllabus.cos": "Write each course outcome and choose its level of Bloom's Taxonomy. A level is suggested from "
                    "the first word.",
    "syllabus.map": "In the CO-PO-PSO mapping, choose 1, 2 or 3 for each outcome against each PO and PSO, and type "
                    "the articulation figure for each column.",
    "syllabus.content": "Then the course content, module by module, with its hours, the outcomes it serves and its "
                        "Bloom's level, and then the text books, book references and web references.",

    "revision.open": "Course Revision compares each course's previous syllabus with the revised one.",
    "revision.summary": "The summary counts the courses and gives the average percentage of revision.",
    "revision.course": "Further down, each course shows its modules, previous and revised, with the percentage of "
                       "change.",

    "earlier.open": "Earlier batches are chosen at the top. Each has its own Curriculum, Syllabus and Course "
                    "Revision, for the semesters the Office has set for that batch.",
    "earlier.table": "The batch's courses are listed as in the programme structure. The arrows open a course's "
                     "syllabus or its revision.",

    "submit.save": "Everything saves as you type. Here, the objectives have been left empty.",
    "submit.end": "When a stage is complete, scroll to the end of the page and press Submit.",
    "submit.checks": "The portal checks the page first. Anything missing is listed here, and Fill them now takes "
                     "you straight to the box.",
    "submit.fix": "Fill it in, and press Submit again. Once the checks pass, the part is submitted and the next "
                  "one opens.",
    "submit.review": "A programme's last step opens a review of the whole programme: every part, and what is in it.",
    "submit.confirm": "Tick to confirm, and submit. Submitted work goes to the Office of Academic Affairs and "
                      "becomes read-only. Only the Office can send it back for correction.",

    "reports.open": "Reports lists every programme, with what you have submitted.",
    "reports.view": "See your submission shows each Curriculum, Syllabus and Course Revision exactly as the "
                    "Office's Word templates lay them out. It is view only. For a copy, contact the Office of "
                    "Academic Affairs.",

    "more.versions": "Version History shows every saved version, who made it and when. A version can be restored "
                     "as a draft, as long as that part is not yet submitted.",
    "more.password": "Change Password sets a new password for your department's login.",
    "more.help": "And Help brings you back to this video and to the user manual. Thank you.",
}

# the pointer, the ring, the caption and the title card, drawn over every page
OVERLAY_JS = r"""
(() => {
  if (window.__help) return;
  const css = `
  .demo-strip, #btn-sample, .demo-fill { display: none !important; }
  #hx-cursor { position: fixed; left: -40px; top: -40px; width: 26px; height: 26px; z-index: 2147483647;
    pointer-events: none; filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
  #hx-ring { position: fixed; z-index: 2147483646; pointer-events: none; border: 3px solid #f59e0b;
    border-radius: 12px; box-shadow: 0 0 0 6px rgba(245,158,11,.22); opacity: 0; transition: all .35s ease; }
  #hx-cap { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); width: max-content;
    max-width: 1040px; z-index: 2147483645; pointer-events: none; background: rgba(14,42,92,.94); color: #fff;
    font: 600 20px/1.45 Inter, "Segoe UI", system-ui, sans-serif; padding: 12px 24px; border-radius: 14px;
    box-shadow: 0 10px 30px rgba(0,0,0,.28); opacity: 0; transition: opacity .3s; text-align: center; }
  #hx-card { position: fixed; inset: 0; z-index: 2147483647; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center; color: #fff; opacity: 0;
    pointer-events: none; transition: opacity .45s;
    background: radial-gradient(circle at 30% 20%, #1d4ed8 0, #0e2a5c 55%, #081a3a 100%);
    font-family: Inter, "Segoe UI", system-ui, sans-serif; }
  #hx-card .k { font-size: 17px; letter-spacing: .28em; text-transform: uppercase; opacity: .78; }
  #hx-card .t { font-size: 50px; font-weight: 800; margin-top: 14px; max-width: 1100px; line-height: 1.15; }
  #hx-card .s { font-size: 21px; opacity: .85; margin-top: 16px; max-width: 980px; }
  #hx-card .bar { width: 90px; height: 5px; border-radius: 3px; background: #f59e0b; margin-top: 26px; }
  .hx-click { position: fixed; width: 18px; height: 18px; border-radius: 50%; background: rgba(245,158,11,.55);
    z-index: 2147483646; pointer-events: none; transform: translate(-50%,-50%);
    animation: hx-pulse .55s ease-out forwards; }
  @keyframes hx-pulse { to { transform: translate(-50%,-50%) scale(3.6); opacity: 0; } }
  `;
  const arrow = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l15 11-6.5 1.2L16 21l-3 1.4-3.3-6.9L4 20z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const make = () => {
    if (document.getElementById("hx-cursor")) return;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement("div"); c.id = "hx-cursor"; c.innerHTML = arrow; document.body.appendChild(c);
    const r = document.createElement("div"); r.id = "hx-ring"; document.body.appendChild(r);
    const cap = document.createElement("div"); cap.id = "hx-cap"; document.body.appendChild(cap);
    const card = document.createElement("div"); card.id = "hx-card";
    card.innerHTML = '<div class="k"></div><div class="t"></div><div class="s"></div><div class="bar"></div>';
    document.body.appendChild(card);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", make); else make();
  const $ = id => document.getElementById(id);
  document.addEventListener("mousemove", e => {
    const c = $("hx-cursor"); if (c) { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }
  }, true);
  document.addEventListener("mousedown", e => {
    const d = document.createElement("div"); d.className = "hx-click";
    d.style.left = e.clientX + "px"; d.style.top = e.clientY + "px"; document.body.appendChild(d);
    setTimeout(() => d.remove(), 700);
  }, true);
  window.__help = {
    at(x, y) { make(); const c = $("hx-cursor"); c.style.left = x + "px"; c.style.top = y + "px"; },
    cap(text) { make(); const c = $("hx-cap"); if (text) { c.textContent = text; c.style.opacity = 1; } else c.style.opacity = 0; },
    card(k, t, s) { make(); const c = $("hx-card"); c.querySelector(".k").textContent = k;
      c.querySelector(".t").textContent = t; c.querySelector(".s").textContent = s || ""; c.style.opacity = 1; },
    uncard() { const c = $("hx-card"); if (c) c.style.opacity = 0; },
    ring(x, y, w, h) { make(); const r = $("hx-ring"); Object.assign(r.style, { left: x + "px", top: y + "px",
      width: w + "px", height: h + "px", opacity: 1 }); },
    unring() { const r = $("hx-ring"); if (r) r.style.opacity = 0; },
    hide(on) { ["hx-cursor", "hx-ring", "hx-cap", "hx-card"].forEach(id => { const n = $(id); if (n) n.style.visibility = on ? "hidden" : ""; });
      document.querySelectorAll(".toast, .toasts, [class*=toast]").forEach(t => t.style.visibility = on ? "hidden" : ""); },
  };
})();
"""


# ---------------------------------------------------------------------------
# the voice (optional)
# ---------------------------------------------------------------------------

def _clip(text):
    return WORK / "voice" / (hashlib.sha1(f"{VOICE}|{text}".encode()).hexdigest()[:16] + ".mp3")


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def make_voice():
    """Every line spoken, once (kept in WORK/voice between runs)."""
    import asyncio
    import edge_tts
    (WORK / "voice").mkdir(parents=True, exist_ok=True)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    async def one(text, path):
        await edge_tts.Communicate(text, VOICE, rate="-4%", proxy=proxy).save(str(path))

    lines = list(SAY.values()) + [s["title"] for s in SECTIONS]
    for text in lines:
        p = _clip(text)
        if not p.exists() or p.stat().st_size < 1000:
            asyncio.run(one(text, p))
            print("  voice:", text[:60])


# ---------------------------------------------------------------------------
# recording one section
# ---------------------------------------------------------------------------

class Rec:
    """One section's recording: what is said when, the pictures for the manual."""

    def __init__(self, browser, key, state=None, voice=False):
        self.key, self.voice = key, voice
        self.ctx = browser.new_context(viewport=VIEW, record_video_dir=str(WORK / "raw"), record_video_size=VIEW,
                                       storage_state=state, device_scale_factor=1)
        self.ctx.add_init_script(OVERLAY_JS)
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(15000)
        self.t0 = time.monotonic()
        self.begin = None             # where the section starts in its recording (its title card)
        self.cues = []                # (start, end, text, key)
        self.caption = ""
        self.pos = (640, 380)
        self.shots = []

    def t(self):
        return time.monotonic() - self.t0

    def wait(self, s):
        self.page.wait_for_timeout(int(s * 1000))

    def js(self, expr, arg=None):
        """The overlay, on whatever page is up (a click may just have left it)."""
        try:
            return self.page.evaluate(expr, arg)
        except Exception:
            return None

    def _restore(self):
        self.js("([x, y, c]) => { __help.at(x, y); __help.cap(c); }", [self.pos[0], self.pos[1], self.caption])

    def goto(self, path):
        self.page.goto(B + path)
        self.page.wait_for_load_state("networkidle")
        self.wait(0.6)
        self._restore()

    def landed(self):
        """After a click that opens another page."""
        self.page.wait_for_load_state("networkidle")
        self.wait(0.7)
        self._restore()

    def _hold(self, text):
        if self.voice and _clip(text).exists():
            return _duration(_clip(text)) + 0.45
        words = len(text.split())
        return max(2.4, words / 2.5 + 0.6)

    def card(self, kicker, title, sub="", speak=None):
        self.js("([k, t, s]) => { __help.cap(''); __help.card(k, t, s); }", [kicker, title, sub])
        if self.begin is None:
            self.begin = self.t()
        self.wait(0.5)
        start = self.t()
        text = speak or title
        self.wait(max(2.6, self._hold(text)))
        self.cues.append((start, self.t(), text, None))
        self.js("__help.uncard()")
        self.wait(0.6)

    def say(self, key, extra=0.0):
        text = SAY[key]
        self.caption = text
        self.js("t => __help.cap(t)", text)
        start = self.t()
        self.wait(self._hold(text) + extra)
        self.cues.append((start, self.t(), text, key))
        self.quiet()

    def quiet(self):
        self.caption = ""
        self.js("__help.cap('')")

    def _box(self, loc):
        loc = self._one(loc)
        loc.wait_for(state="visible", timeout=8000)
        b = loc.bounding_box()
        return loc, b

    def _one(self, loc):
        return self.page.locator(loc).first if isinstance(loc, str) else loc

    def settle(self):
        """Wait for a smooth scroll to finish (a long page takes a while)."""
        last, still = None, 0
        for _ in range(60):
            now = self.js("() => [scrollX, scrollY]")
            still = still + 1 if now == last else 0
            if still >= 3:
                break
            last = now
            self.wait(0.1)
        self.wait(0.25)

    def scroll_to(self, loc, block="center"):
        loc = self._one(loc)
        loc.wait_for(state="attached", timeout=8000)
        loc.evaluate(f"e => e.scrollIntoView({{behavior: 'smooth', block: '{block}'}})")
        self.wait(0.3)
        self.settle()

    def scroll_by(self, dy):
        self.page.evaluate(f"window.scrollBy({{top: {dy}, behavior: 'smooth'}})")
        self.wait(0.3)
        self.settle()

    def glide(self, x, y):
        x0, y0 = self.pos
        n = max(12, int(math.hypot(x - x0, y - y0) / 18))
        for i in range(1, n + 1):
            k = i / n
            k = k * k * (3 - 2 * k)                       # ease in and out
            self.page.mouse.move(x0 + (x - x0) * k, y0 + (y - y0) * k)
            self.page.wait_for_timeout(12)
        self.pos = (x, y)

    def move(self, loc):
        loc, b = self._box(loc)
        self.glide(b["x"] + min(b["width"] / 2, 220), b["y"] + min(b["height"] / 2, 40))
        return loc, b

    def ring(self, b, pad=6):
        self.js("([x, y, w, h]) => __help.ring(x, y, w, h)",
                [b["x"] - pad, b["y"] - pad, b["width"] + 2 * pad, b["height"] + 2 * pad])

    def unring(self):
        self.js("__help.unring()")

    def point(self, loc, say=None, scroll=True, block="center"):
        try:
            if scroll:
                self.scroll_to(loc, block)
            loc, b = self.move(loc)
            self.ring(self._one(loc).bounding_box())
        except Exception as e:
            print(f"  [{self.key}] could not point at {loc}: {e.__class__.__name__}")
            if say:
                self.say(say)
            return
        if say:
            self.say(say)
        else:
            self.wait(1.0)
        self.unring()

    def click(self, loc, nav=False, scroll=True):
        if scroll:
            self.scroll_to(loc)
        loc, b = self.move(loc)
        self.ring(b)
        self.wait(0.45)
        self.unring()
        self.page.mouse.click(*self.pos)
        if nav:
            self.landed()
        else:
            self.wait(0.6)

    def type(self, loc, text, clear=True):
        self.click(loc)
        if clear:
            self.page.keyboard.press("Control+A")
        self.page.keyboard.type(text, delay=55)
        self.wait(0.4)

    def shot(self, name, loc=None, pad=12, full=False):
        """A picture for the manual, without the pointer and caption."""
        (WORK / "shots").mkdir(parents=True, exist_ok=True)
        path = WORK / "shots" / f"{name}.png"
        self.js("__help.hide(true)")
        self.wait(0.15)
        try:
            if loc is not None:
                b = self._one(loc).bounding_box()
                clip = {"x": max(0, b["x"] - pad), "y": max(0, b["y"] - pad),
                        "width": min(VIEW["width"], b["width"] + 2 * pad),
                        "height": min(VIEW["height"], b["height"] + 2 * pad)}
                self.page.screenshot(path=str(path), clip=clip)
            else:
                self.page.screenshot(path=str(path), full_page=full)
        except Exception as e:                       # a missing picture must not end the recording
            print(f"  could not take {name}: {str(e).splitlines()[0][:120]}")
            return
        finally:
            self.js("__help.hide(false)")
        self.shots.append(name)

    def close(self):
        video = self.page.video
        self.ctx.close()
        return {"key": self.key, "video": video.path(), "begin": self.begin or 0.0, "cues": self.cues,
                "end": self.t()}


# ---------------------------------------------------------------------------
# the sections
# ---------------------------------------------------------------------------

def card(r, n):
    s = SECTIONS[n - 1]
    r.card(f"Section {n}", s["title"], s["sub"], speak=f"Section {n}. {s['title']}.")


def sec_start(r, login):
    r.goto("/")
    r.card("BoS Academic Portal · JAIN (Deemed-to-be University)", "How the portal works",
           "A walkthrough for departments · Office of Academic Affairs", speak=SAY["start.intro"])
    card(r, 1)
    r.point(".login-card, form[action$='/login'], input[name=username]", "start.signin", scroll=False)
    r.type("input[name=username]", login[0])
    r.type("input[name=password]", login[1])
    r.shot("start_login")
    r.click("form button[type=submit]", nav=True)
    if "/who" in r.page.url:
        r.point("form", "start.who", scroll=False)
        r.type("input[name=name]", "Dr. Asha Rao")
        r.type("input[name=email]", "asha.rao@jainuniversity.ac.in")
        r.shot("start_who")
        r.click("form button[type=submit]", nav=True)
    if "/department/" not in r.page.url:
        r.goto("/department/")
    r.shot("start_home")
    r.point(".resume-card", "start.home", scroll=False)
    r.point(".home-next", None, scroll=False)
    r.point(".subs-card", "start.progress")
    r.scroll_by(-800)
    r.point(".side-nav", "start.side", scroll=False)


def sec_dept(r):
    r.goto("/department/stage/dept_info")
    card(r, 2)
    r.point("#sec-identity", "dept.open", scroll=False)
    r.shot("dept_identity", "#sec-identity")
    r.scroll_to("#sec-programmes_offered", "start")
    r.point("#sec-programmes_offered", "dept.progs", scroll=False)
    r.shot("dept_programmes")
    r.point("text=Add UG programme", "dept.add")
    r.point(".savebar", "dept.save")


def sec_prebos(r):
    r.goto("/department/stage/pre_bos")
    card(r, 3)
    r.point(".field[data-field=diac_signed] > label", "prebos.open", scroll=False)
    r.point(".field[data-field=diac_signed] .tpl-link", "prebos.template")
    r.point(".field[data-field=diac_signed] .upload-folder", "prebos.upload")
    r.scroll_to(".field[data-field=diac_signed] .tpl-check", "center")
    r.shot("prebos_upload", ".field[data-field=diac_signed]")
    r.point(".field[data-field=diac_signed] .tpl-check", None, scroll=False)
    r.point(".field[data-field=diac_signed] .kw-match", "prebos.check")
    r.point(".field[data-field=pre_bos_minutes] .file-preview", "prebos.card")


def sec_bosdocs(r):
    r.goto("/department/stage/bos_documents")
    card(r, 4)
    r.point("#sec-meeting", "bosdocs.open", scroll=False)
    r.shot("bosdocs_top")
    r.point("#sec-bos_files", "bosdocs.list", block="start")
    r.point("#sec-bos_files .req", "bosdocs.req")


def sec_curriculum(r):
    r.goto("/department/stage/curriculum")
    card(r, 5)
    r.point(".lvl-tabs", "curriculum.list", scroll=False)
    r.shot("curriculum_list")
    r.click("text=BBA in Demonstration Management", nav=True)
    r.point(".pflow-row", "curriculum.parts", scroll=False)
    r.point("#sec-details", "curriculum.details")
    r.point(".field[data-field=objective]", "curriculum.objective")
    r.scroll_to(".field[data-field=programme_outcomes]", "start")
    r.shot("curriculum_outcomes")
    r.point(".field[data-field=programme_outcomes] .ol-foot button", None, scroll=False)
    r.say("curriculum.pos")
    r.point(".field[data-field=selection_procedure]", "curriculum.regs")
    r.scroll_to("#sec-semester_structure", "start")
    r.shot("curriculum_structure")
    r.point("#sec-semester_structure", "curriculum.structure", scroll=False)
    r.scroll_to("#sec-credit_classification", "start")
    r.shot("curriculum_credits")
    r.point("#sec-credit_classification", "curriculum.credits", scroll=False)
    r.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    r.wait(0.3)
    r.settle()
    r.point(".ugc-strip", None, scroll=False)


def sec_syllabus(r):
    r.goto("/department/stage/prog_syllabus/DEMOBBA")
    card(r, 6)
    r.point(".syl-nav", "syllabus.open")
    r.shot("syllabus_nav")
    r.point("table.sh-info", None)
    r.shot("syllabus_info", "table.sh-info")
    r.point(".sheet-wrap:visible [data-field=objectives]", "syllabus.objectives")
    r.point("table.sh-cot", "syllabus.cos")
    r.shot("syllabus_cos", "table.sh-cot")
    r.point("table.sh-map", None)
    r.shot("syllabus_map", "table.sh-map")
    r.say("syllabus.map")
    r.point("table.sh-syl", "syllabus.content", block="start")
    r.shot("syllabus_content")


def sec_revision(r):
    r.goto("/department/stage/prog_revision/DEMOBBA")
    card(r, 7)
    r.point(".pflow-row", "revision.open", scroll=False)
    r.point("#sec-revision_summary", "revision.summary", block="start")
    r.shot("revision_summary")
    r.point("#sec-courses", "revision.course", block="start")
    r.shot("revision_courses")


def sec_earlier(r):
    r.goto("/department/stage/prog_curriculum/DEMOBBA")
    card(r, 8)
    r.click("text=2024–2025", nav=True)
    r.point(".pflow-row", "earlier.open", scroll=False)
    r.shot("earlier_batch")
    r.point("#sec-batch_courses", "earlier.table", block="start")


def sec_submit(r):
    # the B.Com programme's Curriculum, its objectives left empty
    r.goto("/department/stage/prog_curriculum/DEMOBCOM")
    card(r, 9)
    box = ".field[data-field=objective] textarea"
    r.scroll_to(box)
    r.type(box, "")
    r.page.keyboard.press("Delete")
    r.point(".field[data-field=objective]", "submit.save", scroll=False)
    r.scroll_to("#btn-submit", "center")
    r.point("#btn-submit", "submit.end", scroll=False)
    r.click("#btn-submit", scroll=False)
    r.wait(2.0)
    r.shot("submit_checks")
    r.point(".rv-modal .rv-panel", "submit.checks", scroll=False)
    # "Fill them now" takes you to the box
    fill = r.page.get_by_role("button", name="Fill them now")
    if fill.count():
        r.click(fill, scroll=False)
        r.wait(1.2)
    r.type(box, "To give students a sound grounding in accounting and finance.\n"
                "To prepare them for careers in industry and for higher study.", clear=False)
    r.say("submit.fix")
    r.wait(1.0)                                      # saved
    r.click("#btn-submit")
    r.page.wait_for_url("**/prog_syllabus/**", timeout=20000)
    r.landed()
    # the programme's last step (its last earlier batch): the review of the whole programme
    r.goto("/department/stage/prog_syllabus_b2025/DEMOBCOM")
    r.scroll_to("#btn-submit", "center")
    r.click("#btn-submit", scroll=False)
    r.wait(3.0)
    r.shot("submit_review")
    r.say("submit.review")
    tick = r.page.locator(".rv-terms input").first
    if tick.count():
        r.click(tick, scroll=False)
        r.say("submit.confirm")
        go = r.page.get_by_role("button", name=re.compile(r"^Submit all"))
        if go.count():
            r.click(go, scroll=False)
            r.wait(3.0)
            r.shot("submit_done")
    else:
        r.say("submit.confirm")


def sec_reports(r):
    r.goto("/department/")
    card(r, 10)
    r.click(".side-nav a[href$='/department/reports']", nav=True, scroll=False)
    r.point(".subs-table", "reports.open", scroll=False)
    r.click("a[href*='/programme/DEMOBBA/report']", nav=True)
    r.point(".subm-docs", None, scroll=False)
    r.shot("reports_view")
    r.say("reports.view")
    r.click("a.subm-doc:has-text('Syllabus')", nav=True, scroll=False)
    r.scroll_by(420)
    r.wait(1.0)


def sec_more(r):
    r.goto("/department/")
    card(r, 11)
    r.click(".side-nav a[href$='/department/versions']", nav=True, scroll=False)
    r.point(".ver-page", "more.versions", scroll=False)
    r.shot("more_versions")
    r.click(".side-nav a[href*='password']", nav=True, scroll=False)
    r.point("form", "more.password", scroll=False)
    r.click(".side-nav a[href$='/department/help']", nav=True, scroll=False)
    r.point("main, .help-watch, .help-manual", "more.help", scroll=False)
    r.card("BoS Academic Portal", "Thank you", "Questions? Write to the Office of Academic Affairs.", speak="Thank you.")


SECTION_RUN = {"start": sec_start, "dept": sec_dept, "prebos": sec_prebos, "bosdocs": sec_bosdocs,
               "curriculum": sec_curriculum, "syllabus": sec_syllabus, "revision": sec_revision,
               "earlier": sec_earlier, "submit": sec_submit, "reports": sec_reports, "more": sec_more}


# ---------------------------------------------------------------------------
# the portal, the demo department, the recordings
# ---------------------------------------------------------------------------

def start_server():
    log = open(WORK / "server.log", "w")
    srv = subprocess.Popen([sys.executable, "tools/devserver.py", str(PORT)], cwd=ROOT, stdout=log,
                           stderr=subprocess.STDOUT, preexec_fn=os.setsid,
                           env={**os.environ, "UPLOAD_ROOT": str(WORK / "uploads")})
    for _ in range(80):
        try:
            urllib.request.urlopen(B + "/", timeout=1)
            return srv
        except Exception:
            time.sleep(0.5)
    raise SystemExit("the portal did not start — see " + str(WORK / "server.log"))


def admin_password():
    sys.path.insert(0, str(ROOT))
    from config import Config  # noqa: E402
    return Config.ADMIN_USERNAME, Config.ADMIN_PASSWORD


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        exe = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome") or [None])[0]
        return p.chromium.launch(executable_path=exe)


def sign_in(page, user, pw):
    page.goto(B + "/")
    page.fill("input[name=username]", user)
    page.fill("input[name=password]", pw)
    page.press("input[name=password]", "Enter")
    page.wait_for_load_state("networkidle")


def record(only=None, voice=False):
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        browser = launch(p)
        # the Office makes the demo department; the department fills it with sample data
        setup = browser.new_context(viewport=VIEW)
        page = setup.new_page()
        sign_in(page, *admin_password())
        text = html.unescape(re.sub(r"<[^>]+>", " ", page.request.post(B + "/admin/demo-department").text()))
        m = re.search(r"Username (\S+), password (\S+?) ", text)
        if not m:
            raise SystemExit("the demo department could not be made")
        login = m.groups()
        dept = browser.new_context(viewport=VIEW)
        dpage = dept.new_page()
        sign_in(dpage, *login)
        if "/department" not in dpage.url and "/who" not in dpage.url:
            raise SystemExit("the demo department could not sign in")
        if "/who" in dpage.url:
            dpage.fill("input[name=name]", "Dr. Asha Rao")
            dpage.fill("input[name=email]", "asha.rao@jainuniversity.ac.in")
            dpage.click("form button[type=submit]")
            dpage.wait_for_load_state("networkidle")
        dpage.request.post(B + "/department/demo/fill-all")
        state = dept.storage_state()

        for n, s in enumerate(SECTIONS, start=1):
            if only and n not in only:
                continue
            if s["key"] == "reports":
                # every part of one programme submitted, so there is something to see
                items = dpage.request.get(B + "/department/api/record?programme=DEMOBBA").json()["items"]
                for it in items:
                    dpage.request.post(B + f"/department/api/{it['key']}/DEMOBBA/submit", data=it["data"])
            print(f"section {n}: {s['title']}")
            r = Rec(browser, s["key"], state=None if s["key"] == "start" else state, voice=voice)
            try:
                if s["key"] == "start":
                    sec_start(r, login)
                else:
                    SECTION_RUN[s["key"]](r)
            finally:
                rec = r.close()
            rec.update(n=n, title=s["title"], sub=s["sub"], shots=r.shots)
            out.append(rec)
        browser.close()
    return out


# ---------------------------------------------------------------------------
# one video, its chapters and captions
# ---------------------------------------------------------------------------

def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def ts(sec, sep="."):
    h, rem = divmod(max(0.0, sec), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", sep)


def assemble(recs, voice=False):
    OUT.mkdir(parents=True, exist_ok=True)
    parts, chapters, vtt, at = [], [], ["WEBVTT", ""], 0.0
    for rec in recs:
        begin = max(0.0, rec["begin"] - 0.05)
        length = rec["end"] - begin
        seg = WORK / f"seg{rec['n']:02d}.mp4"
        cues = [(a - begin, b - begin, text) for a, b, text, _key in rec["cues"]]
        inputs = ["-ss", f"{begin:.3f}", "-t", f"{length:.3f}", "-i", rec["video"]]
        if voice:
            clips = [(a, _clip(text)) for a, _b, text in cues if _clip(text).exists()]
            for _a, c in clips:
                inputs += ["-i", c]
            mix = "".join(f"[{i + 1}:a]adelay={int(a * 1000)}:all=1[a{i}];" for i, (a, _c) in enumerate(clips))
            mix += "".join(f"[a{i}]" for i in range(len(clips))) + \
                f"amix=inputs={len(clips)}:normalize=0,apad,atrim=0:{length:.3f}[aout]"
            ff(*inputs, "-filter_complex", mix, "-map", "0:v", "-map", "[aout]",
               "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "26",
               "-c:a", "aac", "-b:a", "96k", "-ar", "44100", seg)
        else:
            ff(*inputs, "-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=r=44100:cl=mono",
               "-map", "0:v", "-map", "1:a", "-vf", "fps=25,format=yuv420p", "-c:v", "libx264",
               "-preset", "medium", "-crf", "26", "-c:a", "aac", "-b:a", "48k", "-shortest", seg)
        real = _duration(seg) or length
        chapters.append({"title": rec["title"], "sub": rec["sub"], "start": round(at, 2), "end": round(at + real, 2)})
        for a, b, text in cues:
            vtt += [f"{ts(at + a)} --> {ts(at + b)}", text, ""]
        parts.append(seg)
        at += real
    lst = WORK / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    joined = WORK / "joined.mp4"
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)
    meta = WORK / "chapters.ffmeta"
    meta.write_text(";FFMETADATA1\ntitle=BoS Academic Portal — How it works\n" + "".join(
        f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(c['start'] * 1000)}\nEND={int(c['end'] * 1000)}\n"
        f"title={c['title']}\n" for c in chapters))
    ff("-i", joined, "-i", meta, "-map_metadata", "1", "-map_chapters", "1", "-c", "copy",
       "-movflags", "+faststart", OUT / "walkthrough.mp4")
    ff("-ss", "1.2", "-i", OUT / "walkthrough.mp4", "-frames:v", "1", "-q:v", "3", OUT / "poster.jpg")
    (OUT / "chapters.json").write_text(json.dumps(chapters, indent=1, ensure_ascii=False))
    (OUT / "captions.vtt").write_text("\n".join(vtt))
    return chapters


# ---------------------------------------------------------------------------
# the user manual
# ---------------------------------------------------------------------------

MANUAL = [
    {"key": "start", "intro": "Each department signs in with the username and password the Office of Academic "
     "Affairs issued to it. The portal takes the department's record stage by stage: Department Information, "
     "Pre-BoS, BoS Documents and Curriculum.",
     "steps": ["Open the portal and enter your department's username and password, then press Sign in.",
               "The first time on a computer, give your name and e-mail. Every change you save is noted against them.",
               "Your home page shows the next step: press Continue to carry on where you left off.",
               "Below it are how many stages are done, and your submissions, programme by programme.",
               "The menu on the left opens every stage. A blue dot means in progress; green means submitted."],
     "tips": ["Use “Not you? Switch account” at the foot of the menu when someone else takes over on the same computer.",
              "Forgot the password, or no login yet? Write to the Office of Academic Affairs."],
     "shots": [("start_login", "Signing in"), ("start_who", "Who is filling in"), ("start_home", "The home page")]},
    {"key": "dept", "intro": "Your department's name, faculty, school and campus come from the Office's records. "
     "Here you say which programmes you run this year.",
     "steps": ["Open Department Information from the menu.",
               "Check the department's details at the top. To correct them, write to the Office.",
               "Under Programmes offered, keep each programme you run this year; Remove takes off one you do not.",
               "A programme missing from the list? Use Add UG programme or Add PG programme.",
               "When the list is right, scroll to the end of the page and press Submit."],
     "tips": ["There is no Save button: every change saves itself (the note at the end of the page says when)."],
     "shots": [("dept_identity", "Department identity"), ("dept_programmes", "Programmes offered")]},
    {"key": "prebos", "intro": "Pre-BoS collects the signed composition of the Department Industry-Academia Cell "
     "(DIAC), of the Department Programme Assessment Committee (DPAC), and the minutes of the Pre-BoS meeting.",
     "steps": ["Download each template (“Download the template for reference”), fill it in and sign it.",
               "Upload it: drag the file onto its box, or press Choose file. A Word file, a signed PDF or a "
               "scanned copy are all accepted.",
               "Check what the portal read: a Word form is checked row by row; the keywords show whether it is the "
               "right document.",
               "Open or View shows the file; Remove takes it away so you can upload another."],
     "tips": ["The keyword check is a guide only. A scanned copy, or a category that does not apply, does not stop you submitting."],
     "shots": [("prebos_upload", "An uploaded composition form, with its checks")]},
    {"key": "bosdocs", "intro": "BoS Documents holds the date of the Board of Studies meeting and its documents.",
     "steps": ["Enter the date of the BoS meeting.",
               "Upload the composition of BoS members, profiles of the external experts, the minutes, geotagged "
               "photos, the attendance sheet, the vision and mission, and the stakeholder feedback.",
               "A red star marks a document you must upload; the others are optional."],
     "tips": ["Several files can go into one box (for example one profile per expert)."],
     "shots": [("bosdocs_top", "BoS Documents")]},
    {"key": "curriculum", "intro": "The Curriculum stage is filled programme by programme. Each programme has three "
     "parts — Curriculum, Syllabus and Course Revision — for the current batch, and the same for each earlier batch.",
     "steps": ["Open Curriculum, choose UG or PG, and open a programme.",
               "Programme details: the specialisation; the batch is set for you. For a UG programme the degree is "
               "worked out from its structure.",
               "1. Objective: the programme's objectives, one per line.",
               "1.A and 1.B: the Programme Outcomes (POs) and Programme Specific Outcomes (PSOs). Add the next one "
               "with “+ Add PO…”; every course's CO-PO-PSO mapping takes these columns.",
               "Items 2 to 12, the regulations. A box showing grey sample wording may be left empty to accept it.",
               "The programme structure: every course, semester by semester, with its category, L-T-P-E hours, "
               "credits and marks. Semesters 7 and 8 have their own Honours and Honours with Research groups.",
               "The credit tables fill themselves; the UGC Table 2 strip at the top says whether the credits meet "
               "the requirement."],
     "tips": ["Submit the Curriculum, then go on to the Syllabus: the buttons at the top take you between the parts."],
     "shots": [("curriculum_list", "Programmes"), ("curriculum_outcomes", "Objective, POs and PSOs"),
               ("curriculum_structure", "The programme structure"), ("curriculum_credits", "Credits by classification")]},
    {"key": "syllabus", "intro": "The Syllabus has one sheet per course, laid out as the University's sample syllabus.",
     "steps": ["Choose a semester, a course category and a course (or search by code or title).",
               "Course Information — title, code, L-T-P-E, semester, contact hours, credits and CA : ESE — comes "
               "from the Curriculum; change it there.",
               "Course Objectives start from the programme's objectives: change them for the course.",
               "Course Outcomes: write each CO and choose its level of Bloom's Taxonomy (1 to 6). A level is "
               "suggested from the first word.",
               "CO-PO-PSO Mapping: choose 1, 2 or 3 (or –) for each CO against each PO and PSO, and type the "
               "Articulation figure for each column.",
               "Course Content: each module with its title, hours, the COs it serves and its Bloom's level, then "
               "the Text Books, Book References and Web References."],
     "tips": ["“Fill in all courses from the Curriculum” makes a sheet for every course in the structure."],
     "shots": [("syllabus_nav", "Choosing a course"), ("syllabus_info", "Course Information"),
               ("syllabus_cos", "Course Outcomes and Bloom's levels"), ("syllabus_map", "CO-PO-PSO Mapping"),
               ("syllabus_content", "Course Content")]},
    {"key": "revision", "intro": "Course Revision compares each course's previous syllabus with the revised one.",
     "steps": ["The summary counts the courses and gives the average percentage of revision.",
               "Each course shows its modules, previous beside revised, with the percentage of change."],
     "tips": ["A course's revision opens from its row in the programme structure as well."],
     "shots": [("revision_summary", "The summary"), ("revision_courses", "Course by course")]},
    {"key": "earlier", "intro": "Earlier batches have the same three parts, for the semesters the Office has set "
     "for each batch.",
     "steps": ["Choose the batch at the top of a programme's pages (Earlier · 2024–2025 …).",
               "List the batch's courses as in the programme structure; the arrows open a course's syllabus or revision."],
     "tips": [],
     "shots": [("earlier_batch", "An earlier batch")]},
    {"key": "submit", "intro": "Everything saves as you type. When a stage or part is complete, submit it.",
     "steps": ["Scroll to the end of the page and press Submit.",
               "The page is checked first. Anything missing is listed in the Checks panel; each item takes you "
               "straight to its box. Fill it in and press Submit again.",
               "Once the checks pass, the stage or part is submitted and the next one opens.",
               "A programme's last step opens a review of the whole programme: every part, and what is in it. "
               "Tick to confirm and press Submit all.",
               "Submitted work goes to the Office of Academic Affairs and becomes read-only. Only the Office can "
               "send it back for correction; their comments show at the top of the page."],
     "tips": ["Nothing is lost if you stop half-way: everything you typed is saved, and Continue on the home page "
              "brings you back."],
     "shots": [("submit_checks", "The Checks panel lists what is missing"),
               ("submit_review", "Review & submit this programme"), ("submit_done", "Submitted")]},
    {"key": "reports", "intro": "Reports shows what you have submitted.",
     "steps": ["Open Reports from the menu: every programme, with what is submitted.",
               "See your submission shows each Curriculum, Syllabus and Course Revision — current batch and each "
               "earlier batch — as the Office's Word templates lay them out."],
     "tips": ["It is view only. For a copy, contact the Office of Academic Affairs."],
     "shots": [("reports_view", "Your submission")]},
    {"key": "more", "intro": "",
     "steps": ["Version History shows every saved version, who made it and when; a version can be restored as a "
               "draft while that part is not yet submitted.",
               "Change Password sets a new password for your department's login.",
               "Help opens the walkthrough video, section by section, and this manual."],
     "tips": [],
     "shots": [("more_versions", "Version History")]},
]


def manual(chapters):
    from playwright.sync_api import sync_playwright
    shots = WORK / "shots"
    secs = {s["key"]: (n, s) for n, s in enumerate(SECTIONS, start=1)}
    toc = "".join(f'<li><a href="#s{n}"><span>{n}</span>{html.escape(s["title"])}</a></li>'
                  for n, s in enumerate(SECTIONS, start=1))
    body = []
    for m in MANUAL:
        n, s = secs[m["key"]]
        pics = "".join(
            f'<figure><img src="{(shots / (name + ".png")).as_uri()}"><figcaption>{html.escape(cap)}</figcaption></figure>'
            for name, cap in m["shots"] if (shots / (name + ".png")).exists())
        steps = "".join(f"<li>{html.escape(x)}</li>" for x in m["steps"])
        tips = "".join(f"<li>{html.escape(x)}</li>" for x in m["tips"])
        start = next((c["start"] for c in chapters if c["title"] == s["title"]), None)
        video = (f'<p class="vid">In the video: section {n}, from {int(start // 60)}:{int(start % 60):02d}.</p>'
                 if start is not None else "")
        body.append(f"""
        <section id="s{n}">
          <div class="kick">Section {n}</div><h2>{html.escape(s['title'])}</h2>
          {f'<p class="lead">{html.escape(m["intro"])}</p>' if m["intro"] else ''}
          <ol class="steps">{steps}</ol>
          {f'<div class="tips"><strong>Good to know</strong><ul>{tips}</ul></div>' if tips else ''}
          {video}
          {pics}
        </section>""")
    logo = (ROOT / "app" / "static" / "img" / "jain-logo.png").as_uri()
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>BoS Academic Portal — User manual</title>
<style>
  @page {{ size: A4; margin: 18mm 16mm 18mm 16mm; }}
  body {{ font-family: Inter, "Segoe UI", Arial, sans-serif; color: #1f2937; font-size: 11pt; line-height: 1.5; }}
  .cover {{ height: 245mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always;
    background: linear-gradient(160deg, #0e2a5c, #1d4ed8); color: #fff; margin: -18mm -16mm 0; padding: 0 22mm; }}
  .cover img {{ width: 150px; background: #fff; border-radius: 10px; padding: 8px 12px; }}
  .cover .k {{ margin-top: 40px; letter-spacing: .25em; text-transform: uppercase; font-size: 10pt; opacity: .8; }}
  .cover h1 {{ font-size: 34pt; margin: 10px 0 6px; line-height: 1.1; }}
  .cover p {{ font-size: 13pt; opacity: .9; max-width: 140mm; }}
  .cover .bar {{ width: 70px; height: 5px; background: #f59e0b; border-radius: 3px; margin: 22px 0; }}
  .toc {{ page-break-after: always; }}
  .toc h2 {{ color: #0e2a5c; }}
  .toc ol {{ list-style: none; padding: 0; }}
  .toc li {{ margin: 0 0 6px; }}
  .toc a {{ display: flex; gap: 12px; align-items: center; padding: 9px 12px; border: 1px solid #dbe3ee;
    border-radius: 10px; color: #0e2a5c; text-decoration: none; font-weight: 600; }}
  .toc a span {{ width: 26px; height: 26px; border-radius: 50%; background: #0e2a5c; color: #fff; display: grid;
    place-items: center; font-size: 9pt; }}
  section {{ page-break-before: always; }}
  section:first-of-type {{ page-break-before: auto; }}
  .kick {{ color: #b45309; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; font-size: 9pt; }}
  h2 {{ color: #0e2a5c; font-size: 20pt; margin: 4px 0 10px; }}
  .lead {{ font-size: 11.5pt; color: #374151; }}
  .steps {{ padding-left: 20px; }}
  .steps li {{ margin: 0 0 6px; }}
  .tips {{ border-left: 4px solid #f59e0b; background: #fff8eb; padding: 8px 12px; border-radius: 6px; margin: 10px 0; }}
  .tips ul {{ margin: 4px 0 0; padding-left: 18px; }}
  .vid {{ color: #1d4ed8; font-size: 10pt; }}
  figure {{ margin: 12px 0 16px; page-break-inside: avoid; }}
  figure img {{ width: 100%; border: 1px solid #dbe3ee; border-radius: 8px; }}
  figcaption {{ font-size: 9pt; color: #6b7280; margin-top: 4px; }}
</style></head><body>
<div class="cover"><img src="{logo}"><div class="k">JAIN (Deemed-to-be University) · Office of Academic Affairs</div>
  <h1>BoS Academic Portal<br>User manual</h1><div class="bar"></div>
  <p>How a department fills its Board of Studies record, stage by stage — with a picture of each page.
     The walkthrough video, section by section, is under Help in the portal.</p></div>
<div class="toc"><h2>Contents</h2><ol>{toc}</ol></div>
{''.join(body)}
</body></html>"""
    page_html = WORK / "manual.html"
    page_html.write_text(doc, encoding="utf-8")
    with sync_playwright() as p:
        browser = launch(p)
        pg = browser.new_page()
        pg.goto(page_html.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.pdf(path=str(OUT / "manual.pdf"), format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>",
               footer_template='<div style="font-size:8px;color:#6b7280;width:100%;padding:0 16mm;display:flex;'
                               'justify-content:space-between"><span>BoS Academic Portal · User manual</span>'
                               '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
               margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        browser.close()


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--voice", action="store_true", help="speak the captions (edge-tts)")
    ap.add_argument("--only", type=int, nargs="*", help="record these sections only (no video or manual made)")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed")
    if args.only is None:
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if args.voice:
        make_voice()
    srv = start_server()
    try:
        recs = record(only=set(args.only or []) or None, voice=args.voice)
    finally:
        os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
    (WORK / "recs.json").write_text(json.dumps(recs, indent=1, default=str))
    if args.only:
        print("recorded:", [r["video"] for r in recs])
        return
    chapters = assemble(recs, voice=args.voice)
    manual(chapters)
    print("made", OUT / "walkthrough.mp4", f"({sum(c['end'] - c['start'] for c in chapters):.0f} s),",
          OUT / "manual.pdf")


if __name__ == "__main__":
    main()
