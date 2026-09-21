"""The Office of Academics console: the fixes, not the happy path alone."""

import io

import pytest

from tests.test_workflow import make_department


@pytest.fixture()
def admin(app, client):
    client.post("/login", data={"username": app.config["ADMIN_USERNAME"],
                                "password": app.config["ADMIN_PASSWORD"]})
    return client


# --------------------------------------------------------------------------
# department master
# --------------------------------------------------------------------------

def test_a_department_needs_a_name_and_a_school(admin):
    r = admin.post("/admin/departments/new",
                   data={"dept_code": "NEW", "dept_name": "", "school": "",
                         "campus": "Bengaluru"})
    assert r.status_code == 400
    assert "name is required" in r.get_data(as_text=True)


def test_a_department_code_has_to_be_usable_as_a_username(admin):
    r = admin.post("/admin/departments/new",
                   data={"dept_code": "not a code!", "dept_name": "X",
                         "school": "Y", "campus": "Bengaluru"})
    assert r.status_code == 400
    assert "cannot be a department code" in r.get_data(as_text=True)


def test_a_rejected_form_comes_back_filled_in(admin):
    r = admin.post("/admin/departments/new",
                   data={"dept_code": "bad code", "dept_name": "Department of Physics",
                         "school": "School of Sciences", "campus": "Kochi"})
    body = r.get_data(as_text=True)
    assert "Department of Physics" in body and "School of Sciences" in body


def test_a_duplicate_code_names_the_department_holding_it(app, admin):
    make_department(app, "DUP", "Department of Duplicates")
    r = admin.post("/admin/departments/new",
                   data={"dept_code": "DUP", "dept_name": "Another", "school": "S",
                         "campus": "Bengaluru"})
    assert r.status_code == 400
    assert "Department of Duplicates" in r.get_data(as_text=True)


def test_disabling_a_department_is_its_own_form(app, admin):
    """A nested <form> is dropped by the browser, so the button did nothing."""
    make_department(app, "TOG", "Department of Toggles")
    body = admin.get("/admin/departments/TOG/edit").get_data(as_text=True)
    # the toggle form must not sit inside the details form
    details_form = body.index('<form method="post">')
    toggle_form = body.index('/admin/departments/TOG/toggle')
    closing = body.index("</form>", details_form)
    assert closing < toggle_form, "the toggle form is still nested inside the edit form"


def test_disabling_a_department_disables_its_login(app, admin, dbx):
    make_department(app, "OFF", "Department of Offswitches")
    admin.post("/admin/departments/OFF/toggle", follow_redirects=True)
    assert dbx.departments.find_one({"dept_code": "OFF"})["active"] is False
    assert dbx.users.find_one({"dept_code": "OFF"})["active"] is False


def test_renaming_a_department_carries_its_login_and_records(app, admin, dbx):
    make_department(app, "OLD", "Department of Old Names")
    admin.post("/admin/departments/OLD/edit",
               data={"dept_code": "NEW", "dept_name": "Department of New Names",
                     "school": "School of Commerce", "campus": "Bengaluru", "active": "on"},
               follow_redirects=True)
    assert dbx.departments.find_one({"dept_code": "NEW"})
    user = dbx.users.find_one({"username": "old"})
    assert user["dept_code"] == "NEW"
    assert user["name"] == "Department of New Names"


# --------------------------------------------------------------------------
# credentials
# --------------------------------------------------------------------------

def test_bulk_generation_catches_a_blank_username(app, admin, dbx):
    make_department(app, "BLK", "Department of Blanks")
    dbx.departments.update_one({"dept_code": "BLK"}, {"$set": {"username": ""}})
    admin.post("/admin/credentials/bulk", follow_redirects=True)
    assert dbx.departments.find_one({"dept_code": "BLK"})["username"]


def test_bulk_generation_says_so_when_there_is_nothing_to_do(admin):
    r = admin.post("/admin/credentials/bulk", follow_redirects=True)
    assert "already has a login" in r.get_data(as_text=True)


def test_the_department_list_can_actually_copy_a_password(app, admin):
    make_department(app, "CPY", "Department of Copies")
    admin.post("/admin/departments/CPY/credentials", follow_redirects=True)
    body = admin.get("/admin/departments").get_data(as_text=True)
    assert "data-copy=" in body
    assert "js/copy.js" in body, "the copy buttons have no script behind them"


# --------------------------------------------------------------------------
# the Excel import
# --------------------------------------------------------------------------

def _workbook(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Department", "Code", "School", "Campus"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_a_large_import_preview_survives_the_round_trip(admin, dbx):
    """The preview used to be stuffed into a 4 KB session cookie."""
    rows = [(f"Department number {i}", f"D{i:03d}", "School of Scale", "Bengaluru")
            for i in range(300)]
    r = admin.post("/admin/import", data={"workbook": (_workbook(rows), "big.xlsx")},
                   content_type="multipart/form-data")
    assert r.status_code == 200
    assert "D299" in r.get_data(as_text=True)

    codes = [f"D{i:03d}" for i in range(300)]
    r = admin.post("/admin/import/commit",
                   data={"include": codes}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "no longer available" not in body
    assert dbx.departments.count_documents({"school": "School of Scale"}) == 300


def test_an_import_generates_a_login_for_a_department_it_skipped(app, admin, dbx):
    make_department(app, "SKP", "Department of Skips")
    dbx.departments.update_one({"dept_code": "SKP"}, {"$unset": {"username": ""}})
    dbx.users.delete_many({"dept_code": "SKP"})
    admin.post("/admin/import",
               data={"workbook": (_workbook([("Department of Skips", "SKP",
                                              "School of Commerce", "Bengaluru")]),
                                  "one.xlsx")},
               content_type="multipart/form-data")
    admin.post("/admin/import/commit", data={"include": ["SKP"], "make_logins": "on"},
               follow_redirects=True)
    assert dbx.departments.find_one({"dept_code": "SKP"}).get("username")


def test_an_empty_sheet_is_reported_not_previewed(admin):
    r = admin.post("/admin/import", data={"workbook": (_workbook([]), "empty.xlsx")},
                   content_type="multipart/form-data", follow_redirects=True)
    assert "No department rows" in r.get_data(as_text=True)


# --------------------------------------------------------------------------
# the submission monitor
# --------------------------------------------------------------------------

def test_the_monitor_lists_a_department_that_has_not_started(app, admin):
    make_department(app, "IDL", "Department of Idlers")
    body = admin.get("/admin/submissions").get_data(as_text=True)
    assert "Department of Idlers" in body
    assert "Not started" in body


def test_opening_a_record_does_not_create_one(app, admin, dbx):
    make_department(app, "RDO", "Department of Read Only")
    admin.get("/admin/submissions/RDO")
    assert dbx.submissions.count_documents({"dept_code": "RDO"}) == 0


def test_an_unlocked_stage_really_opens(app, admin, client, dbx):
    """The override wrote a status that nothing read."""
    from app.workflow import compute_status
    make_department(app, "UNL", "Department of Unlocks")
    admin.post("/admin/submissions/UNL/meeting_docs/unlock", follow_redirects=True)
    sub = dbx.submissions.find_one({"dept_code": "UNL"})
    assert compute_status(sub, "meeting_docs") == "open"


def test_an_override_can_be_undone(app, admin, dbx):
    from app.workflow import compute_status
    make_department(app, "RLK", "Department of Relocks")
    admin.post("/admin/submissions/RLK/meeting_docs/unlock", follow_redirects=True)
    admin.post("/admin/submissions/RLK/meeting_docs/relock", follow_redirects=True)
    sub = dbx.submissions.find_one({"dept_code": "RLK"})
    assert compute_status(sub, "meeting_docs") == "locked"


def test_a_stage_that_does_not_exist_is_a_404(app, admin):
    make_department(app, "NOP", "Department of Nopes")
    assert admin.post("/admin/submissions/NOP/not_a_stage/unlock").status_code == 404


def test_a_return_needs_a_reason(app, admin):
    make_department(app, "RSN", "Department of Reasons")
    r = admin.post("/admin/submissions/RSN/dept_info/return", data={"note": " "},
                   follow_redirects=True)
    assert "Say what needs correcting" in r.get_data(as_text=True)


# --------------------------------------------------------------------------
# rules and settings
# --------------------------------------------------------------------------

def test_a_nonsense_total_does_not_crash_the_rules_form(admin, dbx):
    r = admin.post("/admin/rules", data={"total.ug3": "one hundred", "total.ug4": "160"},
                   follow_redirects=True)
    assert r.status_code == 200
    assert "not accepted" in r.get_data(as_text=True)
    assert dbx.rules.find_one({"_id": "ugc"})["totals"]["ug3"] == 120


def test_a_maximum_below_the_minimum_is_refused(admin, dbx):
    r = admin.post("/admin/rules",
                   data={"total.ug3": "120", "total.ug4": "160",
                         "major_core.ug3.min": "60", "major_core.ug3.max": "10"},
                   follow_redirects=True)
    assert "below the minimum" in r.get_data(as_text=True)
    row = next(x for x in dbx.rules.find_one({"_id": "ugc"})["table2"]
               if x["key"] == "major_core")
    assert row["ug3"]["max"] is None


def test_the_academic_year_cannot_be_emptied(admin, dbx):
    r = admin.post("/admin/settings", data={"academic_year": "  "})
    assert r.status_code == 400
    assert dbx.settings.find_one({"_id": "app"})["academic_year"] == "2027-28"


def test_a_valid_year_is_saved_and_reported(admin, dbx):
    r = admin.post("/admin/settings",
                   data={"academic_year": "2030-31", "submissions_open": "on"},
                   follow_redirects=True)
    assert "2030-31" in r.get_data(as_text=True)
    assert dbx.settings.find_one({"_id": "app"})["academic_year"] == "2030-31"


# --------------------------------------------------------------------------
# audit log
# --------------------------------------------------------------------------

def test_the_audit_log_is_reachable_from_the_navigation(admin):
    assert "/admin/audit" in admin.get("/admin/").get_data(as_text=True)


def test_the_audit_log_filters_and_pages(admin, dbx):
    from app.db import now
    dbx.audit.insert_many([{"actor": "someone.else", "action": "login.ok", "target": "",
                            "detail": {}, "at": now()} for _ in range(150)])
    body = admin.get("/admin/audit?actor=someone.else").get_data(as_text=True)
    assert "Page 1 of" in body
    page2 = admin.get("/admin/audit?actor=someone.else&page=2").get_data(as_text=True)
    assert "Page 2 of" in page2
