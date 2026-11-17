"""A summary of a PDF made on the server itself — no AI service, no key, no
limits, nothing leaves the university.

It cannot understand a document the way a language model does. It picks out
what BoS documents are made of — what kind of document it is, the dates in
it, the people named with their roles, the programmes, the resolutions — and
says plainly when the PDF is a scan it cannot read.
"""

from __future__ import annotations

import re

NAME = "Built-in reader"

# what a document is, from the words in it — first match wins
KINDS = [
    ("Minutes of a meeting", r"\bminutes\b|\bproceedings\b"),
    ("Attendance sheet", r"\battendance\b|\bpresent\b.*\bsignature\b"),
    ("DIAC composition", r"\bDIAC\b|industry[- ]academi[ac] (advisory )?committee"),
    ("DPAC composition", r"\bDPAC\b|programme assessment committee|program assessment committee"),
    ("BoS composition", r"\bcomposition\b|\bconstitution of\b.*\bboard\b"),
    ("Vision, mission and programme overview", r"\bvision\b.*\bmission\b|\bmission\b.*\bvision\b"),
    ("Profile / CV", r"\bcurriculum vitae\b|\bresume\b|\bprofile\b|\bqualifications?\b.*\bexperience\b"),
    ("Stakeholder feedback", r"\bfeedback\b|\bsurvey\b|\bquestionnaire\b"),
    ("Syllabus", r"\bsyllabus\b|\bcourse outcomes?\b|\bmodule\s*[1iI]\b"),
    ("Curriculum / programme structure", r"\bcurriculum\b|\bprogramme structure\b|\bcredits?\b.*\bsemester\b"),
    ("Course revision log", r"\brevision\b.*\bcourse\b|\bcourse\b.*\brevision\b"),
    ("Invoice or bill", r"\binvoice\b|\bbill to\b|\bamount due\b|\bGSTIN\b"),
]

# what the upload box expects, from its label → a pattern the text should match
EXPECT = [
    (r"minutes", r"\bminutes\b|\bproceedings\b|\bresolved\b"),
    (r"attendance", r"\battendance\b|\bpresent\b|\bsignature\b"),
    (r"\bdiac\b", r"\bDIAC\b|industry|advisory"),
    (r"\bdpac\b", r"\bDPAC\b|assessment"),
    (r"composition", r"\bmember|\bchair"),
    (r"vision", r"\bvision\b|\bmission\b"),
    (r"profile", r"\bprofile\b|\bexperience\b|\bqualification|\bdesignation\b"),
    (r"syllabus", r"\bsyllabus\b|\bmodule\b|\boutcome"),
    (r"curriculum", r"\bcurriculum\b|\bcredit|\bsemester\b"),
    (r"revision", r"\brevision\b|\brevised\b"),
    (r"feedback", r"\bfeedback\b|\bsurvey\b|\bresponse"),
]

MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
          "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")
DATE = re.compile(
    rf"\b(\d{{1,2}}[./-]\d{{1,2}}[./-](?:19|20)\d{{2}}"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\.?,?\s+(?:19|20)\d{{2}}"
    rf"|(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{{2}})\b", re.I)
ROLE = re.compile(r"\b(chair(?:person|man)?|member[- ]secretary|convener|convenor|external (?:member|expert)"
                  r"|subject expert|industry expert|alumni?|student (?:member|representative)"
                  r"|dean|director|hod|head of (?:the )?department|special invitee|member)\b", re.I)
PERSON = re.compile(r"\b(?:Dr|Prof|Mr|Mrs|Ms|Shri|Smt)\.?\s+[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3}")
PROGRAMME = re.compile(r"\b(?:B\.?\s?Tech|M\.?\s?Tech|B\.?\s?Com|M\.?\s?Com|BBA|MBA|BCA|MCA|B\.?\s?Sc|M\.?\s?Sc"
                       r"|B\.?\s?A|M\.?\s?A|B\.?\s?Des|M\.?\s?Des|Ph\.?\s?D|B\.?\s?Pharm|LLB|LLM)\b"
                       r"(?:\s*(?:\(|in\s+|-\s*)[A-Z][A-Za-z &]{2,40}\)?)?")
RESOLVED = re.compile(r"^\s*(?:it (?:is|was) )?(?:resolved|approved|decided|recommended|agreed)\b.*", re.I | re.M)


def _clean(s: str, n: int = 110) -> str:
    s = re.sub(r"\s+", " ", s).strip(" .;:-–—•\t")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _unique(items, limit):
    seen, out = set(), []
    for it in items:
        k = re.sub(r"\W+", "", it.lower())
        if k and k not in seen:
            seen.add(k)
            out.append(it)
        if len(out) >= limit:
            break
    return out


def kind_of(text: str) -> str | None:
    head = text[:6000]
    for kind, pat in KINDS:
        if re.search(pat, head, re.I | re.S):
            return kind
    return None


def summarise_text(text: str, pages: int, label: str, name: str) -> str:
    """A few lines about the document, from its text layer."""
    body = re.sub(r"--- page \d+ ---", "", text)
    lines = [l.strip() for l in body.splitlines() if l.strip()]

    kind = kind_of(body)
    title = next((_clean(l, 90) for l in lines[:12] if 12 <= len(l) <= 140 and not DATE.fullmatch(l)), "")
    first = f"{kind or 'Document'} — {pages} page{'s' if pages != 1 else ''}"
    if title:
        first += f". Headed “{title}”"
    out = [first + "."]

    dates = _unique([_clean(d, 30) for d in DATE.findall(body)], 4)
    if dates:
        out.append("- Dates: " + ", ".join(dates))

    people = []
    for l in lines:
        if ROLE.search(l) and (PERSON.search(l) or len(l) < 90):
            people.append(_clean(l, 90))
    people = _unique(people, 5)
    members = len(re.findall(r"\bmember\b", body, re.I))
    if people:
        out.append("- People and roles: " + "; ".join(people))
    elif members:
        out.append(f"- “Member” appears {members} time{'s' if members != 1 else ''}")

    progs = _unique([_clean(p, 50) for p in PROGRAMME.findall(body)], 4)
    if progs:
        out.append("- Programmes: " + ", ".join(progs))

    resolved = _unique([_clean(r, 120) for r in RESOLVED.findall(body)], 3)
    if resolved:
        out.append("- Decisions: " + " | ".join(resolved))

    if len(out) == 1 and lines:          # nothing matched: say how it opens
        out.append("- Opens with: " + _clean(" ".join(lines[:3]), 160))

    out.append("Check: " + _check(body, label, kind))
    return "\n".join(out)


def _check(body: str, label: str, kind: str | None) -> str:
    notes = []
    want = next((pat for key, pat in EXPECT if re.search(key, label, re.I)), None)
    if want and not re.search(want, body, re.I):
        notes.append(f"nothing in it looks like “{label}” — make sure this is the right file")
    if kind == "Invoice or bill":
        notes.append("it reads like an invoice, not a BoS document")
    if not DATE.search(body) and re.search(r"minutes|attendance|composition", label, re.I):
        notes.append("no date found")
    if not notes:
        return "nothing stands out — open it to confirm."
    s = "; ".join(notes)
    return s[0].upper() + s[1:] + "."


def scan_note(pages: int) -> str:
    return (f"Scanned PDF — {pages} page{'s' if pages != 1 else ''} of pictures with no text in them.\n"
            "The built-in reader can only read PDFs that have text. Open it with View to check it, "
            "or set up an AI service (AI_API_KEY in .env) to have scans read.\n"
            "Check: open it to confirm it is the right document.")
