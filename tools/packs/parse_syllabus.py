"""
Parse a JAIN syllabus document into course records.

The input is the plain-text / markdown rendering of the department's syllabus
.docx (what Google Drive's text export gives): a "Course Information" table per
course followed by Course Objectives, Course Outcomes, Course Content (or a
list of experiments for a lab), Book References and Web References.

    python tools/packs/parse_syllabus.py syllabus.txt out.json
"""

import json
import re
import sys

LABELS = {"course title": "title", "course code": "code", "l-t-p-e": "ltpe", "semester": "semester",
          "contact hours": "contact_hours", "credits": "credits", "ca:ese": "ca_ese", "ca: ese": "ca_ese"}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def clean(s):
    s = s.replace("\\_", " ").replace("\\-", "-").replace("\\*", "").replace("\\", "")
    s = s.replace("**", "").replace("–", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def table_rows(block):
    out = []
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            out.append([clean(c) for c in line.strip("|").split("|")])
    return out


def info(rows):
    d = {}
    for r in rows:
        cells = [c for c in r]
        i = 0
        while i < len(cells):
            key = LABELS.get(cells[i].lower().strip(" :"))
            if key:
                nxt = cells[i + 1] if i + 1 < len(cells) else ""
                if LABELS.get(nxt.lower().strip(" :")):
                    d.setdefault(key, "")
                    i += 1
                    continue
                d.setdefault(key, nxt)
                i += 2
                continue
            i += 1
    return d


def section(text, start, stops):
    m = re.search(start, text, re.I)
    if not m:
        return ""
    rest = text[m.end():]
    end = len(rest)
    for s in stops:
        n = re.search(s, rest, re.I)
        if n and n.start() < end:
            end = n.start()
    return rest[:end]


def paras(s):
    out = []
    for line in s.split("\n"):
        line = clean(line.lstrip("#").strip())
        if not line or line.startswith("|") or set(line) <= set("-|: "):
            continue
        out.append(line)
    return out


def semester(v):
    v = clean(v).lower().replace("th", "").replace("semester", "").strip()
    if v.isdigit():
        return int(v)
    return ROMAN.get(v)


def num(v):
    m = re.search(r"\d+(\.\d+)?", v or "")
    return float(m.group()) if m else None


def peos(text):
    """The Program Educational Objectives table at the top of the document."""
    out = []
    for r in table_rows(section(text, r"Program Educational Objectives[^\n]*", [r"COURSE SYLLABUS"])):
        if len(r) >= 2 and re.match(r"^PEO\s*\d+$", r[0], re.I):
            out.append(r[1])
    return out


def parse(text):
    parts = re.split(r"\n#*\s*Course Information:?\s*\n", text)
    courses = []
    for block in parts[1:]:
        head = block[:1500]
        d = info(table_rows(head.split("Course Objectives")[0]))
        objectives = paras(section(block, r"Course Objectives:?", [r"Course Outcomes"]))
        co_rows = table_rows(section(block, r"Course Outcomes[^\n]*", [r"CO-PO", r"Course Content"]))
        outcomes = []
        for r in co_rows:
            if len(r) >= 2 and re.match(r"^CO\s*\d+$", r[0], re.I):
                outcomes.append(clean(r[1]))
        stops = [r"Book References", r"Basic References", r"Text ?Books", r"\nReferences:",
                 r"Web References"]
        content = section(block, r"Course Content:?", stops)
        lab = False
        if not content.strip():
            content = section(block, r"1\s*-\s*Low[^\n]*", stops + [r"\n#*\s*SEMESTER\s+\w+\s*\n"])
            lines = paras(content)
            if lines and re.search(r"list of|experiment|program", lines[0], re.I) and len(lines[0]) < 60:
                content = content.split(lines[0].split()[-1], 1)[1] if lines[0].split() else content
            lab = bool(content.strip())
        # Modules as the syllabus sheet holds them: {title, hours, revised}.
        # A lab's experiments are one module, one experiment per line.
        modules = []
        if lab:
            numbered = bool(re.search(r"^\s*1\\?\.\s", content, re.M))
            items = []
            for line in paras(content):
                e = re.match(r"^(\d{1,2})\s*[.)]\s+(.*)$", line)
                if e:
                    items.append(f"{e.group(1)}. {e.group(2)}")
                elif numbered and items:
                    items[-1] += " " + line
                else:
                    items.append(line)
            if items:
                modules.append({"title": "List of experiments", "hours": "",
                                "revised": "\n".join(items)})
        else:
            cur = None
            for line in paras(content):
                m = re.match(r"^(Module|Unit|Part)\s*[-:]?\s*([0-9IVX]+)\s*[:.\-]?\s*(.*)$", line, re.I)
                if m:
                    title, hours = m.group(3), ""
                    hrs = re.search(r"\(?\s*(\d+)\s*(Hours|Hrs|Hr|Hour)\s*\)?\.?$", title, re.I)
                    if hrs:
                        title, hours = title[:hrs.start()].strip(" -–:()"), int(hrs.group(1))
                    cur = {"title": title.strip(" :()") or f"Module {m.group(2)}", "hours": hours,
                           "lines": []}
                    modules.append(cur)
                elif cur is not None:
                    cur["lines"].append(line)
                else:
                    cur = {"title": line, "hours": "", "lines": []}
                    modules.append(cur)
            modules = [{"title": m["title"], "hours": m["hours"], "revised": "\n".join(m["lines"])}
                       for m in modules]
        refs = section(block, r"\n#*\s*(Book References|Basic References|Text ?Books|References)\s*:?[^\n]*\n",
                       [r"Web References", r"\n#*\s*SEMESTER\s+\w+\s*\n"])
        books = [p for p in paras(refs) if not p.lower().startswith("please note")
                 and not p.lower().startswith("references") and len(p) > 8]
        web = paras(section(block, r"Web References:?", [r"\n#*\s*SEMESTER\s+\w+\s*\n", r"\Z"]))
        web = [w for w in web if not re.match(r"^SEMESTER\s+\w+$", w, re.I)]
        ca, ese = None, None
        m = re.findall(r"\d+", d.get("ca_ese", ""))
        if len(m) >= 2:
            ca, ese = int(m[0]), int(m[1])
        code = d.get("code", "")
        if code.lower() in ("new course", "new", "-", "na"):
            code = ""
        courses.append({
            "title": clean(d.get("title", "")),
            "code": re.sub(r"\s+", "", code) if "/" not in code else code,
            "ltpe": d.get("ltpe", ""),
            "semester": semester(d.get("semester", "")),
            "contact_hours": num(d.get("contact_hours")),
            "credits": num(d.get("credits")),
            "ca": ca, "ese": ese,
            "objectives": objectives,
            "outcomes": outcomes,
            "modules": modules,
            "books": books,
            "web": web,
        })
    return courses


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    cs = parse(open(src).read())
    json.dump(cs, open(dst, "w"), indent=1, ensure_ascii=False)
    for c in cs:
        print(f"{str(c['semester']):>4} {c['code']:<28} {c['ltpe']:<9} cr={c['credits']} "
              f"ca={c['ca']}/{c['ese']} hrs={c['contact_hours']} o={len(c['outcomes'])} "
              f"m={len(c['modules'])} b={len(c['books'])} w={len(c['web'])} | {c['title'][:50]}")
