"""The top bar's right side: the portal, the year, light / dark, a bell with
a count, and the signed-in person's initial."""

from test_workflow import login, make_department


def test_the_department_bar_has_the_portal_year_bell_and_initial(app, client):
    from app.db import get_db
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/").get_data(as_text=True)
    assert 'class="erp-portal">Board of Studies Portal' in page
    assert 'class="erp-year">2027–28' in page or 'class="erp-year">2027-28' in page
    assert 'class="erp-bell" href="/department/progress"' in page and "erp-bell-count" not in page
    assert 'class="erp-avatar"' in page and "data-theme-toggle" in page
    # a stage sent back for correction: the bell counts it
    with app.app_context():
        get_db().submissions.update_one({"dept_code": "COM"}, {"$set": {"stages.dept_info.status": "returned"}},
                                        upsert=False)
    page = client.get("/department/").get_data(as_text=True)
    assert 'class="erp-bell-count">1<' in page


def test_the_office_bar_rings_for_new_updates(app, client):
    from app.db import get_db
    client.get("/logout")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    with app.app_context():
        from app.db import now
        get_db().notifications.insert_one({"read": False, "dept_code": "COM", "event": "saved", "text": "x",
                                           "at": now()})
    page = client.get("/admin/").get_data(as_text=True)
    assert 'class="erp-bell" href="/admin/updates"' in page and 'class="erp-bell-count">1<' in page


def test_the_bar_carries_the_page_tabs(app, client):
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/").get_data(as_text=True)
    assert 'id="erp-tabs"' in page and 'data-home="/department/"' in page and "js/tabs.js" in page


def test_the_tabs_work_like_browser_tabs():
    """A tab opens only with + (on Home); pages gone to stay in the open tab."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "app/static/js/tabs.js").read_text()
    assert "sessionStorage" in js and 'url: HOME, title: "Home"' in js
    assert "tabs.push({ url: here" not in js          # going to a page never makes a new tab
