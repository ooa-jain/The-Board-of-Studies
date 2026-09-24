"""Static URLs carry a version stamp so deploys are not hidden by browser caches."""

import re


def test_stylesheet_url_is_versioned(client):
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'/static/css/app\.css\?v=\d+', html)
