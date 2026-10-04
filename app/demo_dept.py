"""One made-up department the Office can sign in as and look at from the
admin side: "Department of Demonstration Studies" (code DEMO).

It is filled the way a real department would fill it — Department
Information and Pre-BoS submitted, BoS Documents half done — with small
PDFs that carry real words, so the keyword check, the summaries and the
updates feed all have something to show. Making it again wipes the old one
first. It is marked `demo: True` everywhere and named so nobody mistakes it.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from .db import get_db, issue_department_login, now

CODE = "DEMO"
NAME = "Department of Demonstration Studies"

DEPT = {
    "dept_code": CODE, "dept_name": NAME,
    "faculty": "Faculty of Demonstration", "school": "School of Demonstration",
    "campus": "Jain Global Campus", "place": "Bangalore",
    "hod_name": "Dr. Demo Head", "hod_email": "demo.head@example.edu",
    "hod_phone": "9000000000", "hod_designation": "Head of the Department",
    "active": True, "demo": True,
}

PROGRAMMES = [
    {"programme_code": "DEMOBBA", "programme_name": "BBA in Demonstration Management",
     "degree": "UG", "source": "new", "decision": "keep"},
    {"programme_code": "DEMOMBA", "programme_name": "MBA in Demonstration Analytics",
     "degree": "PG", "source": "new", "decision": "keep"},
]

# file name → (stage, field, lines of text inside it)
DOCS = {
    "diac.pdf": ("pre_bos", "diac_signed", [
        "Composition of the Department Industry-Academia Cell (DIAC)",
        "Department of Demonstration Studies, 2027-28",
        "Dr. Demo Head, Chairperson", "Ms. Asha Rao, Industry Member, Demo Industries Ltd",
        "Mr. Kiran Shetty, Member, Academia", "Signed: Chairperson, DIAC"]),
    "dpac.pdf": ("pre_bos", "dpac_signed", [
        "Composition of the Department Programme Assessment Committee (DPAC)",
        "Committee members for 2027-28", "Dr. Demo Head, Chairperson",
        "Prof. Leela Iyer, Member", "Dr. Arun Nair, Member Secretary"]),
    "minutes.pdf": ("bos_documents", "minutes", [
        "Minutes of the Board of Studies Meeting",
        "Department of Demonstration Studies, held on 12 March 2027 at 10:00 am",
        "Members present: Dr. Demo Head, Chairperson; Prof. Leela Iyer, External Member",
        "Agenda item 1: curriculum for the BBA in Demonstration Management",
        "Resolved that the BBA curriculum for 2027-28 be approved.",
        "Approved two new electives in the MBA programme."]),
    "bos_composition.pdf": ("bos_documents", "bos_composition", [
        "Composition of the Board of Studies (BoS)", "Dr. Demo Head, Chairperson",
        "Prof. Leela Iyer, External Member", "Mr. Vikram Das, Alumni Member",
        "Ms. Priya Menon, Student Member"]),
    # deliberately the wrong document in the box: an invoice where the
    # vision and mission should be — the keyword check should say so
    "vision_mission.pdf": ("bos_documents", "vision_mission", [
        "INVOICE No. 4471", "Bill to: Demo Stationery Supplies",
        "A4 paper, 20 reams", "Amount due: Rs. 5,400", "GSTIN 29ABCDE1234F1Z5"]),
}


def _pdf(lines):
    """A one-page PDF with these lines in Helvetica — enough for the text
    layer to be read, with no library needed to make it."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    y, ops = 780, ["BT", "/F1 11 Tf"]
    for i, line in enumerate(lines):
        size = 14 if i == 0 else 11
        ops.append(f"/F1 {size} Tf 1 0 0 1 60 {y} Tm ({esc(line)}) Tj")
        y -= 24 if i == 0 else 18
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def remove(db=None):
    db = db or get_db()
    user = db.users.find_one({"dept_code": CODE, "role": "department"})
    for col in ("submissions", "files", "notifications"):
        db[col].delete_many({"dept_code": CODE})
    db.users.delete_many({"dept_code": CODE, "role": "department"})
    db.departments.delete_many({"dept_code": CODE})
    return user


def create(year, upload_root, actor="system"):
    """Make (or remake) the demo department; returns (username, password)."""
    from .keyword_match import check
    from .summarise import field_label
    from .workflow import save_draft, submit_stage

    db = get_db()
    remove(db)
    t = now()
    db.departments.insert_one({**DEPT, "created_at": t, "updated_at": t})
    dept = db.departments.find_one({"dept_code": CODE})
    username, password = issue_department_login(db, dept, actor=actor)
    # as if it had been signed in to and worked on an hour ago
    db.users.update_one({"username": username}, {"$set": {"last_login": t - timedelta(minutes=45)}})

    files = {}
    for name, (stage, field, lines) in DOCS.items():
        folder = upload_root / year / CODE / stage
        folder.mkdir(parents=True, exist_ok=True)
        stored = f"{uuid.uuid4().hex[:12]}-{name}"
        path = folder / stored
        path.write_bytes(_pdf(lines))
        match = check(path, field, field_label(stage, field))
        db.files.insert_one({"dept_code": CODE, "academic_year": year, "stage": stage,
                             "field": field, "original_name": name, "stored_name": stored,
                             "size": path.stat().st_size, "uploaded_by": username,
                             "uploaded_at": t, "keyword_match": match, "demo": True})
        files[field] = {"name": name, "stored": stored, "size": path.stat().st_size,
                        "url": f"/department/file/{stage}/{stored}",
                        "thumb": f"/department/file/{stage}/{stored}?thumb=1", "match": match}

    dept_info = {
        "identity": {"dept_name": NAME, "faculty": DEPT["faculty"], "school": DEPT["school"],
                     "campus": DEPT["campus"], "academic_year": year},
        "contact": {"office_email": "demo.office@example.edu", "faculty_count": 18},
        "programmes_offered": PROGRAMMES,
    }
    results = {}
    _, _, results["dept_info"] = submit_stage(CODE, year, "dept_info", dept_info, actor=username)
    _, _, results["pre_bos"] = submit_stage(
        CODE, year, "pre_bos",
        {"pre_bos_files": {"diac_signed": files["diac_signed"], "dpac_signed": files["dpac_signed"]}},
        actor=username)
    # BoS Documents: started, not finished
    save_draft(CODE, year, "bos_documents", {
        "meeting": {"bos_date": "2027-03-12"},
        "bos_files": {"minutes": files["minutes"], "bos_composition": files["bos_composition"],
                      "vision_mission": files["vision_mission"]}})

    _demo_updates(db, dept, t)
    return username, password, results


def _demo_updates(db, dept, t):
    """A short history in the Updates feed, as if the department had just
    been working. Not sent to any connector."""
    base = {"dept_code": CODE, "dept_name": NAME, "campus": DEPT["campus"],
            "programme_code": "", "programme_name": "", "read": False, "saves": 1,
            "actor": "demo", "demo": True}
    rows = [
        (40, "submitted", "dept_info", "Department Information",
         [{"section": "Programmes offered", "field": "Rows", "before": "0", "after": "2"},
          {"section": "Contact", "field": "Office email", "before": "—", "after": "demo.office@example.edu"}]),
        (25, "submitted", "pre_bos", "Pre-BoS",
         [{"section": "Signed composition documents", "field": "DIAC", "before": "—", "after": "file: diac.pdf"}]),
        (12, "uploaded", "bos_documents", "BoS Documents", []),
        (8, "keyword_miss", "bos_documents", "BoS Documents", []),
        (3, "saved", "bos_documents", "BoS Documents",
         [{"section": "BoS meeting", "field": "Date of the BoS meeting", "before": "—", "after": "2027-03-12"}]),
    ]
    texts = {
        "uploaded": "“minutes.pdf” for Minutes of Meeting — keywords match (minutes, meeting, resolved, agenda)",
        "keyword_miss": "“vision_mission.pdf” for Department Vision, Mission and Program Overview — no expected keywords found",
    }
    from .notify import EVENTS
    for mins, event, stage, title, changes in rows:
        at = t - timedelta(minutes=mins)
        text = f"{NAME} — {EVENTS[event][0]}: {title}"
        if event in texts:
            text += ". " + texts[event]
        elif changes:
            text += f" ({len(changes)} field{'s' if len(changes) != 1 else ''})"
        db.notifications.insert_one({**base, "event": event, "stage": stage, "stage_title": title,
                                     "changes": changes, "text": text, "at": at, "first_at": at})
