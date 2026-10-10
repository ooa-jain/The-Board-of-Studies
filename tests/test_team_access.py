"""Settings › Team & access: people the Office adds, what each may do, and
which departments each sees."""

import re

from test_workflow import DEPT_INFO_OK, login, make_department


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def _add(app, office, email, preset="reviewer", scope="selected", codes=(), schools=(), sections=None,
         delete=False, password=None):
    """Add a person through the form; returns the password from the slip."""
    from app.access import PRESETS, SECTION_KEYS
    secs = sections or PRESETS.get(preset, {}).get("sections") or {}
    form = {"name": email.split("@")[0].title(), "email": email, "preset": preset, "scope": scope,
            "pw_mode": "type" if password else "generate", "password": password or ""}
    for k in SECTION_KEYS:
        form["sec_" + k] = secs.get(k) or "none"
    if delete:
        form["delete"] = "on"
    from werkzeug.datastructures import MultiDict
    data = MultiDict(list(form.items()) + [("codes", c) for c in codes] + [("schools", s) for s in schools])
    r = office.post("/admin/team/new", data=data)
    assert r.status_code == 302 and "/slip" in r.location, r.get_data(as_text=True)[:400]
    slip = office.get(r.location).get_data(as_text=True)
    m = re.search(r'aria-label="Copy the password"', slip)
    assert m, "the slip shows the password"
    import html
    pw = html.unescape(re.search(r'data-copy="([^"]+)" aria-label="Copy the password"', slip).group(1))
    return pw, slip


def _sign_in_fresh(app, email, pw):
    """Their first sign-in: set their own password, then carry on."""
    c = app.test_client()
    r = login(c, email, pw)
    assert r.status_code == 302
    r = c.get("/admin/")
    assert r.status_code == 302 and "change-password" in r.location
    c.post("/change-password", data={"current": pw, "new": "MyOwnPassword9!", "confirm": "MyOwnPassword9!"})
    return c


def _two_departments(app):
    make_department(app)                                                   # COM, School of Commerce
    make_department(app, code="ENG", name="Department of English", school="School of Humanities")


def test_a_full_admin_adds_a_person_and_hands_over_a_slip(app, client):
    _two_departments(app)
    _admin(app, client)
    page = client.get("/admin/team").get_data(as_text=True)
    assert "Team &amp; access" in page and "First admin" in page
    pw, slip = _add(app, client, "priya@jainuniversity.ac.in", codes=["COM"])
    assert "priya@jainuniversity.ac.in" in slip and "Copy as message" in slip and "mailto:" in slip
    assert "Reviewer" in slip and "1 department" in slip
    # shown once
    again = client.get("/admin/team/priya@jainuniversity.ac.in/slip")
    assert again.status_code == 302
    listed = client.get("/admin/team").get_data(as_text=True)
    assert "priya@jainuniversity.ac.in" in listed and "Own password not set yet" in listed
    # the username is the email, whatever case it is typed in
    c = app.test_client()
    assert login(c, "Priya@JainUniversity.ac.in", pw).status_code == 302


def test_a_reviewer_sees_only_their_departments_and_only_comments(app, client):
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "rev@jainuniversity.ac.in", codes=["COM"])
    me = _sign_in_fresh(app, "rev@jainuniversity.ac.in", pw)

    home = me.get("/admin/").get_data(as_text=True)
    assert "Department of Commerce" in home and "Department of English" not in home
    # their menu: no Settings
    assert 'title="Settings"' not in home and 'title="Overview"' in home
    assert me.get("/admin/submissions/COM").status_code == 200
    assert me.get("/admin/submissions/ENG").status_code == 403
    assert me.get("/admin/export/ENG.xlsx").status_code == 403
    assert "Department of English" not in me.get("/admin/submissions").get_data(as_text=True)
    # settings and the team are not theirs
    assert me.get("/admin/settings").status_code == 403
    assert me.get("/admin/team").status_code == 403
    # View on the Overview: they cannot send a stage back …
    r = me.post("/admin/submissions/COM/dept_info/return", data={"note": "Fix it"})
    assert r.status_code == 403
    # … but Edit on Comments: they can comment, on their departments only
    r = me.post("/admin/comments", data={"dept": "COM", "stage": "dept_info", "text": "Please add the HoD's phone."})
    assert r.status_code == 302
    r = me.post("/admin/comments", data={"dept": "ENG", "stage": "dept_info", "text": "Not yours"})
    with app.app_context():
        from app.db import get_db
        assert {c["dept_code"] for c in get_db().comments.find()} == {"COM"}


def test_only_the_sections_given_show_in_the_menu(app, client):
    """'Only Departments and reports' — the rest is hidden and refused."""
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "dr@jainuniversity.ac.in", preset="custom", scope="all",
                 sections={"departments": "view", "overview": "view"})
    me = _sign_in_fresh(app, "dr@jainuniversity.ac.in", pw)
    # no Home for them: they land on the first section they have
    r = login(app.test_client(), "dr@jainuniversity.ac.in", "MyOwnPassword9!")
    assert r.location.endswith("/admin/departments")
    page = me.get("/admin/departments").get_data(as_text=True)
    for shown in ('title="Departments"', 'title="Overview"'):
        assert shown in page, shown
    for hidden in ('title="Home"', 'title="Calendar"', 'title="Flow 3D"', 'title="Comments"', 'title="Settings"'):
        assert hidden not in page, hidden
    assert me.get("/admin/").status_code == 403
    assert me.get("/admin/calendar").status_code == 403
    assert me.get("/admin/sheets?tab=comments").status_code == 403
    assert me.get("/admin/sheets?tab=programmes").status_code == 200
    # View on Departments: cannot issue a login
    assert me.post("/admin/departments/COM/credentials").status_code == 403


def test_delete_needs_its_own_tick(app, client):
    _two_departments(app)
    _admin(app, client)
    secs = {"home": "view", "departments": "edit", "overview": "edit"}
    pw1, _ = _add(app, client, "nodel@jainuniversity.ac.in", preset="custom", scope="all", sections=secs)
    pw2, _ = _add(app, client, "del@jainuniversity.ac.in", preset="custom", scope="all", sections=secs, delete=True)
    a = _sign_in_fresh(app, "nodel@jainuniversity.ac.in", pw1)
    b = _sign_in_fresh(app, "del@jainuniversity.ac.in", pw2)
    assert a.post("/admin/departments/COM/wipe", data={"confirm": "COM"}).status_code == 403
    assert b.post("/admin/departments/COM/wipe", data={"confirm": "COM"}).status_code == 302
    # emptying the whole master is for a Full admin only
    assert b.post("/admin/departments/clear", data={"confirm": "REMOVE ALL"}).status_code == 403


def test_a_whole_school_takes_in_departments_added_later(app, client):
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "hum@jainuniversity.ac.in", schools=["School of Humanities"])
    me = _sign_in_fresh(app, "hum@jainuniversity.ac.in", pw)
    assert me.get("/admin/submissions/ENG").status_code == 200
    assert me.get("/admin/submissions/COM").status_code == 403
    make_department(app, code="HIS", name="Department of History", school="School of Humanities")
    assert me.get("/admin/submissions/HIS").status_code == 200


def test_turning_someone_off_signs_them_out_at_the_next_click(app, client):
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "gone@jainuniversity.ac.in", scope="all")
    me = _sign_in_fresh(app, "gone@jainuniversity.ac.in", pw)
    assert me.get("/admin/").status_code == 200
    client.post("/admin/team/gone@jainuniversity.ac.in/toggle")
    r = me.get("/admin/")
    assert r.status_code == 302 and "/admin/" not in r.location
    assert login(app.test_client(), "gone@jainuniversity.ac.in", "MyOwnPassword9!").location.endswith("#signin")
    # removed for good
    client.post("/admin/team/gone@jainuniversity.ac.in/delete")
    with app.app_context():
        from app.db import get_db
        assert get_db().users.find_one({"username": "gone@jainuniversity.ac.in"}) is None


def test_access_changes_apply_from_the_next_click(app, client):
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "grow@jainuniversity.ac.in", codes=["COM"])
    me = _sign_in_fresh(app, "grow@jainuniversity.ac.in", pw)
    assert me.get("/admin/submissions/ENG").status_code == 403
    edit = client.get("/admin/team/grow@jainuniversity.ac.in/edit").get_data(as_text=True)
    assert 'value="COM" checked' in edit
    from app.access import PRESETS, SECTION_KEYS
    form = {"name": "Grow", "preset": "reviewer", "scope": "all"}
    form.update({"sec_" + k: PRESETS["reviewer"]["sections"].get(k) or "none" for k in SECTION_KEYS})
    assert client.post("/admin/team/grow@jainuniversity.ac.in/edit", data=form).status_code == 302
    assert me.get("/admin/submissions/ENG").status_code == 200


def test_links_in_downloads_can_be_kept_to_the_signed_in_team(app, client):
    from app.share import report_token
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "eng@jainuniversity.ac.in", codes=["ENG"])
    me = _sign_in_fresh(app, "eng@jainuniversity.ac.in", pw)
    with app.app_context():
        url = "/share/r/" + report_token("COM", "BCMREG", "2027-28")
    stranger = app.test_client()
    # anyone with the link, as before …
    assert stranger.get(url).status_code != 302
    # … until the Office keeps them to the team
    client.post("/admin/team/links", data={"share_links": "team"})
    r = stranger.get(url)
    assert r.status_code == 302 and "next=" in r.location
    assert me.get(url).status_code == 403                    # not one of their departments
    assert client.get(url).status_code != 403                # the first admin sees everything
    dept = app.test_client()
    login(dept, "com", "DeptPassword1!")
    assert dept.get(url).status_code != 403                  # the department's own link
    other = app.test_client()
    login(other, "eng", "DeptPassword1!")
    assert other.get(url).status_code == 403


def test_a_department_cannot_reach_the_team_pages(app, client):
    u, p = make_department(app)
    login(client, u, p)
    client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK)
    assert client.get("/admin/team").status_code == 403


def test_motion_and_the_live_home_keep_to_a_person_s_departments(app, client):
    import json, re
    _two_departments(app)
    _admin(app, client)
    pw, _ = _add(app, client, "one@jainuniversity.ac.in", codes=["COM"])
    me = _sign_in_fresh(app, "one@jainuniversity.ac.in", pw)
    page = me.get("/admin/motion").get_data(as_text=True)
    data = json.loads(re.search(r"window.MOTION_DATA = (\{.*?\});</script>", page, re.S).group(1))
    assert data["totals"]["departments"] == 1 and data["scope"] == "Your 1 department"
    home = me.get("/admin/").get_data(as_text=True)
    assert "Department of English" not in home and "the departments you can see" in home
    # no Home, no Motion
    pw2, _ = _add(app, client, "nohome@jainuniversity.ac.in", preset="custom", scope="all",
                  sections={"departments": "view"})
    other = _sign_in_fresh(app, "nohome@jainuniversity.ac.in", pw2)
    assert other.get("/admin/motion").status_code == 403
