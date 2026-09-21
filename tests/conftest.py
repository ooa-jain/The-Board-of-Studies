"""Test fixtures. Uses mongomock so the suite runs without a MongoDB server."""

import os
import sys
from pathlib import Path

import mongomock
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SECRET_KEY", "test-key")
os.environ.setdefault("ADMIN_USERNAME", "ooa.admin")
os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPassword1!")
os.environ.setdefault("ACADEMIC_YEAR", "2027-28")
os.environ.setdefault("UPLOAD_ROOT", str(ROOT / "tests" / "_uploads"))


def _build(monkeypatch, **config):
    from app import db as database
    monkeypatch.setattr(database, "MongoClient",
                        lambda *a, **kw: mongomock.MongoClient())
    from app import create_app
    application = create_app()
    application.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    application.config.update(config)
    return application


@pytest.fixture()
def app(monkeypatch):
    yield _build(monkeypatch)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def test_mode_app(monkeypatch):
    """The portal running as a sandbox."""
    yield _build(monkeypatch, TEST_MODE=True)


@pytest.fixture()
def test_mode_client(test_mode_app):
    return test_mode_app.test_client()


@pytest.fixture()
def csrf_app(monkeypatch):
    """A portal with CSRF enforcement live, as a deployment has it.

    TESTING stays off so the check is not waived; the suite has to carry a
    token exactly as a browser does.
    """
    application = _build(monkeypatch)
    application.config.update(TESTING=False, CSRF_PROTECT=True)
    yield application


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


@pytest.fixture()
def dbx(app):
    from app.db import get_db
    with app.app_context():
        yield get_db()
