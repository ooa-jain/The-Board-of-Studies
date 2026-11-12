"""Light and dark on every page, and Data Flow as a 2D tree beside the 3D view."""

from pathlib import Path

import pytest

from test_workflow import login, make_department

ROOT = Path(__file__).resolve().parents[1]


def _admin(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])


def test_every_page_carries_the_light_dark_switch(app, client):
    # the sign-in page: a floating switch
    page = client.get("/").get_data(as_text=True)
    assert "data-theme-toggle" in page and "theme-float" in page
    assert "css/dark.css" in page and 'media="screen"' in page and "js/theme.js" in page
    # set before the first paint, so a dark page never flashes white
    head = page.split("</head>")[0]
    assert 'setAttribute("data-theme"' in head and head.index("data-theme") < head.index("css/dark.css")
    # the Office's pages and a department's: in the top bar
    _admin(app, client)
    assert 'class="erp-bar-end"><button class="theme-toggle"' in client.get("/admin/").get_data(as_text=True)
    client.get("/logout")
    u, p = make_department(app)
    login(client, u, p)
    assert "data-theme-toggle" in client.get("/department/").get_data(as_text=True)


def test_the_dark_theme_covers_the_stylesheets_and_is_current():
    """dark.css is made from the light stylesheets; it must be made again
    whenever they change."""
    tinycss2 = pytest.importorskip("tinycss2")  # noqa: F841
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_dark_css", ROOT / "tools" / "make_dark_css.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    before = (ROOT / "app/static/css/dark.css").read_text()
    mod.main()
    assert (ROOT / "app/static/css/dark.css").read_text() == before, "run python tools/make_dark_css.py"
    assert 'html[data-theme="dark"] .ad-kpi' in before and 'html[data-theme="dark"] .side-link' in before


def test_data_flow_opens_as_a_2d_tree_with_3d_beside_it(app, client):
    make_department(app)
    _admin(app, client)
    page = client.get("/admin/flow").get_data(as_text=True)
    assert 'id="flow-tree"' in page and 'data-view-btn="2d"' in page and 'data-view-btn="3d"' in page
    assert "js/flow-tree.js" in page and "js/flow3d.js" in page
    assert page.index("js/flow-tree.js") < page.index("js/flow3d.js")
    # the menu calls it Data Flow now
    assert 'title="Data Flow"' in page and "Flow 3D" not in page
    data = client.get("/admin/flow.json?dept=COM").get_json()
    assert data["nodes"][0]["key"] == "dept_info" and data["flows"]
