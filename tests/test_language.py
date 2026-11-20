"""Language, in the department's sidebar: the portal's own words in Hindi,
Kannada, Tamil or Malayalam, kept per browser; English by default; the
Office's pages and what departments type stay as they are."""

import json
import re
from pathlib import Path

from test_workflow import login, make_department

ROOT = Path(__file__).resolve().parent.parent


def test_english_by_default_and_a_choice_in_the_sidebar(app, client):
    u, p = make_department(app)
    login(client, u, p)
    page = client.get("/department/").get_data(as_text=True)
    assert 'class="side-lang"' in page
    for label in ("English", "हिन्दी", "ಕನ್ನಡ", "தமிழ்", "മലയാളം"):
        assert label in page
    assert '<html lang="en"' in page and "js/i18n.js" not in page


def test_picking_a_language_keeps_it_and_loads_its_words(app, client):
    u, p = make_department(app)
    login(client, u, p)
    r = client.post("/language", data={"lang": "kn", "next": "/department/"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/department/")
    assert "bos_lang=kn" in r.headers.get("Set-Cookie", "")
    page = client.get("/department/").get_data(as_text=True)
    assert '<html lang="kn"' in page and "js/i18n.js" in page and "/i18n/kn.js" in page
    assert "Noto+Sans+Kannada" in page
    words = client.get("/i18n/kn.js").get_data(as_text=True)
    assert words.startswith("window.BOS_I18N=") and "ವಿಭಾಗದ ಮಾಹಿತಿ" in words
    # the intro starts in the same language
    app.config["ASK_INTRO"] = True
    try:
        intro = client.get("/department/intro?next=/department/").get_data(as_text=True)
        assert re.search(r'class="intro-lang is-on"[^>]*lang="kn"', intro)
    finally:
        app.config["ASK_INTRO"] = False
    # back to English
    client.post("/language", data={"lang": "en", "next": "/department/"})
    assert "js/i18n.js" not in client.get("/department/").get_data(as_text=True)


def test_unknown_language_or_outside_link_is_ignored(client):
    r = client.post("/language", data={"lang": "xx", "next": "https://example.com/"})
    assert r.headers["Location"].endswith("/") and "example.com" not in r.headers["Location"]
    assert "bos_lang" not in r.headers.get("Set-Cookie", "")
    assert client.get("/i18n/en.js").status_code == 404
    assert client.get("/i18n/xx.js").status_code == 404


def test_the_office_stays_in_english(app, client):
    client.set_cookie("bos_lang", "hi")
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/").get_data(as_text=True)
    assert "js/i18n.js" not in page


def test_every_translation_keeps_its_placeholders():
    keys = json.loads((ROOT / "tools" / "i18n" / "keys.json").read_text(encoding="utf-8"))
    for code in ("hi", "kn", "ta", "ml"):
        words = json.loads((ROOT / "app" / "translations" / f"{code}.json").read_text(encoding="utf-8"))
        assert len(words) > 700, code
        for key, text in words.items():
            assert key in keys
            need = len(re.findall(r"\{\w+\}", key))
            assert set(re.findall(r"\{(\d+)\}", text)) == {str(k) for k in range(1, need + 1)}, (code, key)
