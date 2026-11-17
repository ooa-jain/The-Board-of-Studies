"""Help: the walkthrough video, section by section — a section clicked jumps
to it — and the user manual, for every department."""

import json
from pathlib import Path

from test_workflow import login, make_department

HELP = Path(__file__).resolve().parent.parent / "app" / "static" / "help"


def test_the_help_page_lists_the_sections_of_the_video(app, client):
    u, p = make_department(app)
    login(client, u, p)
    home = client.get("/department/").get_data(as_text=True)
    assert 'href="/department/help"' in home                       # in the side menu
    page = client.get("/department/help").get_data(as_text=True)
    assert "How the portal works" in page and "User manual" in page
    if (HELP / "chapters.json").exists():
        chapters = json.loads((HELP / "chapters.json").read_text())
        assert len(chapters) >= 10
        for c in chapters:
            assert c["title"] in page and f'data-start="{c["start"]}"' in page
        assert "/static/help/walkthrough.mp4?v=" in page and "/static/help/manual.pdf?v=" in page
        # the sections follow one another, from the start of the video
        assert chapters[0]["start"] == 0 and all(a["end"] == b["start"] for a, b in zip(chapters, chapters[1:]))
    # the Office's side has its own pages; Help is the departments'
    client.get("/logout")
    assert client.get("/department/help").status_code in (302, 401, 403)
