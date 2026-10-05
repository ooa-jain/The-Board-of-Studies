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


@pytest.fixture()
def app(monkeypatch):
    from app import db as database
    monkeypatch.setattr(database, "MongoClient",
                        lambda *a, **kw: mongomock.MongoClient())

    # Real pymongo refuses `if db:` / `db or …` on a database or a collection;
    # mongomock allows it. Refuse it here too, so the tests catch it.
    def _no_bool(self):
        raise NotImplementedError(f"{type(self).__name__} objects do not implement truth "
                                  "value testing or bool(). Compare with None instead.")
    monkeypatch.setattr(mongomock.database.Database, "__bool__", _no_bool, raising=False)
    monkeypatch.setattr(mongomock.collection.Collection, "__bool__", _no_bool, raising=False)
    from app import create_app
    application = create_app()
    application.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def dbx(app):
    from app.db import get_db
    with app.app_context():
        yield get_db()
