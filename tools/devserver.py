"""
Run the portal with an in-memory database — no MongoDB needed.

    python tools/devserver.py [port]

Everything is wiped when the process stops. Useful for demoing the flow or
checking a template change before deploying. Test mode is on, so the ribbon
shows on every page and any account can be signed into from /test without a
password. Logins are printed on startup all the same.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TEST_MODE", "1")

import mongomock  # noqa: E402

from app import db as database  # noqa: E402

database.MongoClient = lambda *a, **kw: mongomock.MongoClient()

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402
from app.testmode import seed_for_devserver  # noqa: E402


def main():
    app = create_app()
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["TEST_MODE"] = True
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8102

    with app.app_context():
        # The same demo set the test console seeds, so a dev run and a test
        # run are looking at the same institution.
        rows = seed_for_devserver(get_db())
        print("\n  Demo logins")
        print("  " + "-" * 52)
        for username, password, name in rows:
            print(f"  {username:12} {password:16} {name}")
        print(f"\n  admin: {app.config['ADMIN_USERNAME']} / {app.config['ADMIN_PASSWORD']}")
        print(f"  test console: http://127.0.0.1:{port}/test")
        print(f"  http://127.0.0.1:{port}\n")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
