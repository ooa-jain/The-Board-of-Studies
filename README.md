# BoS Data Repository Portal — JAIN OoA

Flask + MongoDB portal that replaces the Word/Excel template round-trip for Board of Studies
submissions. Departments log in, fill typed forms, and the portal applies the UGC credit rules
before anything is accepted.

Built from the **BOS DATA REPOSITORY** Google Sheet (Sheet1 / LINKS / Sheet3) and the UGC
Table 2 credit table.

---

## What it does

**Office of Academics (admin)**

- Department master — add, edit, disable; import the Directors/Deans/HoDs contact workbook
  with keyword-matched column mapping and a preview before commit
- Generates a login per department: username from the department code, a 12-character password
  shown once with copy buttons, a printable slip, a bulk "generate all missing", and a printable
  credential sheet. The password disappears from admin screens the moment the department signs in;
  reset regenerates it
- Submission monitor — a grid of every department against every stage
- Per-stage "return for correction" with a note, and a lock override
- Editable UGC Table 2 and the other numeric rules, with restore-to-published
- Excel export (institution-wide status + credit compliance) and per-department Excel/Word
- Audit log

**Departments**

- 13 stages that unlock in order; the next opens only when the previous is submitted clean
- Every field typed: integers reject letters at the keystroke, emails, dates, patterns for
  course codes and batch years, minimum word and line counts
- Autosave every 1.4 s and on a 25 s heartbeat
- A live checks panel: click an issue to jump to the field
- Repeating tables with minimum row counts and fixed-row tables for the approval chain and
  the twelve planning items
- File uploads for signed copies, minutes, attendance and photographs
- Own Excel and Word download

---

## The stages

| # | Stage | Replaces |
|---|-------|----------|
| 1 | Department Information | — |
| 2 | **Pre-BoS** | Composition of DIAC · Board of Studies · Programme Assessment Committee |
| 3 | BoS Committee Information | Expert Profile_Form.docx |
| 4 | Programme Information | Curriculum Matrix Template, Section A |
| 5 | **Curriculum & Regulations** | Curriculum Matrix Template, Sections B–D (credit engine runs here) |
| 6 | Course Information | [Template] Syllabus.pdf + skill mapping |
| 7 | Course Revision & Mapping | Course Revisions Log_Template_2026.xlsx |
| 8 | Stakeholder Feedback | Stakeholder Input Log |
| 9 | Meeting Documents | Minutes of the Meeting_Template.docx |
| 10 | Approval & Compliance | — |
| 11 | Supporting Documents | — |
| 12 | Design and Development Plan | Design & Development Plan template |
| 13 | Final BoS Repository | — |

Stages 5, 6 and 7 are filled once per programme.

---

## The rules that are enforced

**UGC Table 2** (`app/ugc_rules.py`) — minimum credits per category, 3-year and 4-year columns,
ranges for Value Added Courses (6–8) and Summer Internship (2–4), Research Project not applicable
to 3-year, totals of 120 and 160, and the in-lieu rule: Honours students not undertaking research
do 3 courses for 12 credits.

**Everything else** (`app/validation.py`)

- L-T-P-E reconciles with credits (lecture and tutorial 1:1, practical and experiential 2:1)
- 1 credit = 25 marks; CIA + ESE = total marks
- Course codes unique and well formed; semester within the programme's duration
- Section B category totals equal the sum of the courses listed in Section C
- DIAC minimum 4 with an industry member and one convener; BoS composition minimums and one
  chairperson; PAC minimum 3
- Expert profiles cover every external BoS member
- Course outcomes start with a Bloom's taxonomy verb; CO-PO mapping well formed
- Revisions above 30% need benchmarking; changed courses need a justification
- All six stakeholder groups present; no future-dated feedback
- BoS notice at least 7 days before the meeting; quorum met
- Approval chain runs in order and after the meeting date

Server-side validation is the gate. The browser copy exists to give immediate feedback.

---

## Install

```bash
git clone git@github.com:ooa-jain/jain-bos-portal.git /var/www/jain-bos-portal
cd /var/www/jain-bos-portal
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env          # MONGO_URI, SECRET_KEY, ADMIN_PASSWORD
```

```bash
sudo cp deploy/jain-bos-portal.service /etc/systemd/system/
sudo cp deploy/nginx.conf /etc/nginx/sites-available/bos.juooa.cloud
sudo ln -s /etc/nginx/sites-available/bos.juooa.cloud /etc/nginx/sites-enabled/
sudo mkdir -p /var/log/jain-bos-portal /var/www/jain-bos-portal/uploads
sudo chown -R www-data:www-data /var/log/jain-bos-portal /var/www/jain-bos-portal
sudo systemctl daemon-reload && sudo systemctl enable --now jain-bos-portal
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d bos.juooa.cloud
```

Port **8102**. Updates: `sudo bash deploy/deploy.sh`.

## First run

1. Sign in as the bootstrap admin from `.env` and change the password
2. **Departments → Import from Excel** — upload the Directors/Dy Directors/Deans/HoDs workbook.
   Tick *Generate a login for each new department*
3. **Departments → Credential sheet** — print it, hand the logins out
4. Check **Credit rules** matches the current UGC framework
5. **Settings** — set the academic year and a deadline banner

`python seed.py --logins` loads a starter department list if you would rather not import yet.

## Run locally without MongoDB

```bash
python tools/devserver.py 8102     # in-memory database, demo logins printed on startup
```

## Tests

```bash
python -m pytest tests/ -q          # 35 tests: credit engine, stage locking, auth, exports
```

---

## Layout

```
jain-bos-portal/
├── wsgi.py                 gunicorn entry point
├── config.py
├── seed.py                 starter department list
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py         application factory
│   ├── schema.py           every template as typed field definitions  ← edit this to change forms
│   ├── ugc_rules.py        UGC Table 2 and the numeric rules
│   ├── validation.py       the validation engine
│   ├── workflow.py         stage state machine and the sequential lock
│   ├── db.py               Mongo, indexes, passwords, audit
│   ├── auth.py  admin.py  dept.py  public.py
│   ├── importer.py         contact-directory Excel → departments
│   ├── exporter.py         Excel and Word output
│   ├── templates/
│   └── static/css/app.css  static/js/stage.js
├── deploy/                 systemd unit, nginx site, deploy.sh
├── tools/devserver.py      run with an in-memory database
└── tests/
```

### Adding a field

Edit `app/schema.py`. The renderer, the validator and both exporters read it, so a new field
needs no other change. A new named rule goes in `app/validation.py` as `r_<name>` and is listed
in the section's `rules`.

---

## Notes

- Generated passwords are stored in the clear on the department record **only until first sign-in**,
  so the admin can hand them over. After that only the bcrypt hash remains. Departments should
  change their password after signing in.
- Uploads live outside the repository, under `UPLOAD_ROOT`. Back that up with the database.
- Changing the academic year in Settings starts a fresh cycle; prior years stay intact.

# The-Board-of-Studies
