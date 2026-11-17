# BoS Academic Portal — handoff

Everything another assistant (or developer) needs to carry on with this
project. Read this first, then `README.md`.

## 1. What it is

A web portal for **JAIN (Deemed-to-be University), Office of Academic Affairs**.
Each department fills its **Board of Studies (BoS)** record for an academic
year, stage by stage, and submits it. The Office (admin) watches progress,
reviews, comments, sends back, downloads Excel / Word / ZIP reports, and can
now edit any department's record itself.

- Live: `https://the-board-of-studies.juooa.cloud` (nginx → gunicorn on 127.0.0.1:8102)
- Server folder: `/var/www/jain-bos-portal`, service `jain-bos-portal` (systemd)
- Repository: `ooa-jain/The-Board-of-Studies`
- **The server runs the branch `claude/confident-johnson-z6jdy2`.** `main` is
  behind; the pull request for this branch brings `main` up to date.

### Deploy (on the server)

```
cd /var/www/jain-bos-portal
git pull --ff-only origin claude/confident-johnson-z6jdy2   # or main, once the PR is merged
./venv/bin/pip install -r requirements.txt
sudo systemctl restart jain-bos-portal
```

Use `./venv/bin/pip` / `./venv/bin/python` — system `pip` is locked on Ubuntu
("externally-managed-environment"). nginx serves `/static/` directly with
`expires 30d`; static URLs carry `?v=<mtime>` so a deploy is picked up.

## 2. How the person works (important)

- The user writes short, informal messages, often with screenshots, and in
  capitals. Read for intent; ask a clarifying question (with options) only
  when something is genuinely ambiguous.
- Wants a **simple, clean, professional UI**. **No features they did not ask
  for.** Plain wording on the page ("Submit", "Not this year", "Edit as the
  Office"), Indian English, dates in IST.
- After every change: run the tests, check it in a browser, commit with a
  clear message, push to `claude/confident-johnson-z6jdy2`, and give them the
  four deploy lines above.
- Never paste or ask for secrets in chat. The old MongoDB user
  `jainresearch` (cluster0.9imrqqp) had its password exposed earlier and
  **should be rotated** — remind them until they confirm.

## 3. Stack

Python 3.12, Flask 3, MongoDB (pymongo), Jinja templates, plain JavaScript
(no framework), openpyxl (Excel), python-docx (Word), pypdfium2 + Pillow
(PDF previews and reading), bcrypt, gunicorn + gevent. Tests use pytest with
**mongomock** (no MongoDB needed).

Configuration comes from `.env` on the server (never committed). Names only:
`SECRET_KEY, MONGO_URI, MONGO_DB, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_NAME,
ACADEMIC_YEAR, UPLOAD_ROOT, MAX_CONTENT_MB, FILE_STORE, DRIVE_SCRIPT_URL,
DRIVE_SCRIPT_SECRET, AI_* / XAI_*, SMTP_*, PUBLIC_URL, PORT, SESSION_DAYS,
PERSON_COOKIE_DAYS`.

## 4. Code map

```
app/__init__.py      app factory, context processor (current_user = page_user()), error pages
app/auth.py          login/logout/password; admin_required, department_required,
                     acting() + page_user() (the Office editing as a department)
app/public.py        landing / sign-in page
app/dept.py          the department's pages and JSON API (/department/...):
                     stages, autosave (api_save), submit, uploads, versions, reports, help
app/admin.py         the Office (/admin/...): dashboard, departments, overview,
                     department page, reviews, comments, exports, settings, keywords
app/share.py         shared/document views (/share/...)
app/team.py          Team & access (admin users with sections + department scope)
app/access.py        permissions: ENDPOINTS map (section, view/edit/delete), scope by
                     place/school/campus/department; every new admin route needs an entry
app/schema.py        THE FORM DEFINITIONS: stages, sections, fields, table columns,
                     rules — the page is built from this (stage.js reads it as JSON)
app/workflow.py      submissions, stage status, programmes_of, save_draft, submit_stage,
                     batches, prefill, programme_list/save_programme_list,
                     follow_outcomes (PO/PSO removal keeps mappings aligned)
app/validation.py    server checks per rule name (errors block submit, warnings don't)
app/ugc_rules.py     UGC credit tables, degree tracks (UG 3-yr, Honours, Research, PG)
app/docgen.py        Word documents in the university templates
app/exporter.py      Excel workbooks and Word exports
app/report.py        programme reports / links
app/people.py        Version History (who saved what, kept 5 days)
app/notify.py        "Updates" feed for the Office
app/catalogue.py     programme catalogue (app/data/programmes.json from the OAA workbook)
app/keyword_match.py uploaded-file keyword check (docx + PDF via pypdfium2); Train keywords
app/template_check.py  Word composition forms checked row by row
app/autofill.py, packs.py, drive_store.py   Fill from Drive / data packs, Google Drive storage
app/demo_dept.py     the demo department and its sample answers
app/static/js/stage.js   builds every stage form from the schema; autosave; tables;
                     syllabus sheets; PO/PSO lists; CA+ESE check; checks panel
app/static/js/review.js  read-only review + modal helper (window.Review.modal)
app/static/css/      app.css, shell.css (layout, sidebar), erp.css;
                     dark.css is GENERATED: python3 tools/make_dark_css.py (needs tinycss2)
app/templates/       base.html (both shells: admin sidebar / department sidebar),
                     dept/*, admin/*, share/*
tools/devserver.py   run locally with an in-memory DB:  python3 tools/devserver.py 5000
tools/help_media.py  makes the Help video + user manual PDF (see §7)
tools/copy_db.py     copy the database to another MongoDB
tests/               pytest; conftest.py patches MongoClient with mongomock
```

## 5. Data model (MongoDB collections)

- `departments` — dept_code, dept_name, faculty, school, campus, place, active, username…
- `users` — role `admin` or `department`; admins have `access` (sections) and `scope`
- `submissions` — one per (dept_code, academic_year):
  - `stages.<stage_key>` = {data, status, updated_at, submitted_at, issues, summary}
  - `programmes.<programme_code>.<part_key>` = same shape, per programme
- `versions` (Version History), `notifications`, `comments`, `settings`
  (academic_year, batches, optional uploads, dev_mode…), `rules`, `files`, `connectors`

### Stages (in order)

1. `dept_info` — Department Information (Level 0): identity (from the Office's
   record) + **Programmes offered** (`programmes_offered` rows:
   programme_code, programme_name, degree UG/PG/PG-1Yr/PGD, category,
   year_introduced, source catalogue/new/office, decision keep/remove)
2. `pre_bos` — signed DIAC and DPAC compositions, Pre-BoS minutes (uploads,
   keyword-checked)
3. `bos_documents` — BoS date and the BoS uploads
4. `curriculum` — per programme, parts:
   - `prog_curriculum` — details, profile (objective, 1.A POs, 1.B PSOs,
     regulations), semester structure (L-T-P-E, credits, CA marks, ESE marks,
     total 100, Syllabus/Revision links), credit tables (UGC)
   - `prog_syllabus` — one sheet per course: info, objectives, COs with Bloom
     levels, CO-PO-PSO mapping (1/2/3/–) + Articulation, modules, books
   - `prog_revision` — Course Revision (previous vs revised, % change)
   - `prog_syllabus_bYYYY` — earlier batches (their own courses and syllabi)

Status values: open, draft, submitted, returned, locked, approved.

## 6. Recent work (newest first)

- **Admin → Departments → click a name**: department page with details, an
  academic-year picker (`?year=` — admin `_year()` honours it), programme list
  for that year with Add / Edit / Remove / Put back / Open
  (`admin.department_programme_save`, `department_programme_run`).
- **Edit as the Office** (`admin.department_act`, `admin.act_stop`): sets
  `session["act_as"] = {dept_code, year}`; the department's own pages then
  work for the admin (`auth.acting()`, `auth.page_user()`), any stage is
  editable, a submitted stage stays submitted, saves are recorded as
  "<admin> (Office of Academic Affairs)", an orange bar offers Back to admin.
- **CA + ESE**: TEE renamed ESE (End Semester Examination); both typed (no
  auto-fill); a pop-up when CA + ESE ≠ 100 once the pair is left; server rule
  `marks_add_up` refuses it on submit.
- **PO/PSO**: × on every item (first included); later ones move up and every
  course's mapping/articulation keys move with them (`workflow.follow_outcomes`).
- **Help page** for departments: walkthrough video (11 sections, clickable,
  voice) + user manual PDF in `app/static/help/`.
- PDF keyword check + "Train keywords" from a department's file; optional
  uploads set by the Office; view-only "See your submission" for departments;
  syllabus sheet in the university layout; PO/PSO from the Curriculum drive the
  syllabus mapping columns; UG degree worked out from the structure; earlier
  batches; programme reports; Overview › Faculties; Team & access; PWA; dark mode.

## 7. Help video and manual

`python3 tools/help_media.py` records the walkthrough with Playwright from a
demo department on a local devserver and builds `app/static/help/`
(walkthrough.mp4, chapters.json, captions.vtt, poster.jpg, manual.pdf).
Needs Playwright + Chromium and ffmpeg (a developer machine, not the server).

The voice uses edge-tts (`speech.platform.bing.com`), which the cloud
sandbox could not reach, so: on the **server**
`./venv/bin/pip install edge-tts && HELP_WORK=/tmp/help_work ./venv/bin/python tools/help_media.py --voice-clips`
→ `app/static/help/voice-clips.zip` → download it → on the dev machine
`python3 tools/help_media.py --use-clips voice-clips.zip` → commit the media.
"BoS" is spoken as the letters "B O S" (`_speech()`), captions keep "BoS".

## 8. Tests

```
pip install -r requirements.txt mongomock pytest
python3 -m pytest -q          # ~250 tests, about 8 minutes
```

Browser checks: run `tools/devserver.py`, sign in as the admin from `.env`
(or config defaults), POST `/admin/demo-department`, sign in as the demo
login it prints, POST `/department/demo/fill-all`.

## 9. Conventions

- Every new admin endpoint: add it to `access.ENDPOINTS` (or it is Full-admin only).
- Change a form → change `schema.py` (and `validation.py` rules); stage.js
  renders from it. Keep labels short and plain.
- After CSS changes: `python3 tools/make_dark_css.py`.
- Commit messages: a short title, then bullets saying what the user sees.
- Don't remove or skip tests to get green.
