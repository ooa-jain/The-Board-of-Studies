"""
Run the portal with an in-memory database — no MongoDB needed.

    python tools/devserver.py [port]

Everything is wiped when the process stops. Useful for demoing the flow or
checking a template change before deploying. Logins printed on startup.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mongomock  # noqa: E402

from app import db as database  # noqa: E402

database.MongoClient = lambda *a, **kw: mongomock.MongoClient()

from app import create_app  # noqa: E402
from app.db import (generate_password, get_db, hash_password,  # noqa: E402
                    now, slugify_username)

DEMO = [
    ("School of Commerce and Management", "Department of Commerce", "COM", "Bengaluru"),
    ("School of Commerce and Management", "Department of Business Administration", "BBA", "Bengaluru"),
    ("Faculty of Engineering and Technology", "Department of Computer Science and Engineering",
     "CSE", "Bengaluru"),
    ("School of Sciences", "Department of Physics", "PHY", "Bengaluru"),
    ("School of Humanities and Social Sciences", "Department of English", "ENG", "Bengaluru"),
    ("School of Commerce and Management", "Department of Commerce", "COM-KC", "Kochi"),
    ("School of Sciences", "Department of Computer Science", "CSC-KC", "Kochi"),
]


def main():
    app = create_app()
    app.config["SESSION_COOKIE_SECURE"] = False
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8102

    with app.app_context():
        db = get_db()
        print("\n  Demo logins")
        print("  " + "-" * 52)
        for school, name, code, campus in DEMO:
            db.departments.insert_one({
                "dept_code": code, "dept_name": name, "school": school, "campus": campus,
                "hod_name": "Dr. " + name.split()[-1] + " Head",
                "hod_designation": "Head of the Department",
                "hod_email": f"{code.lower()}.hod@jainuniversity.ac.in",
                "hod_phone": "9900000000",
                "active": True, "created_at": now(), "updated_at": now(),
            })
            username = slugify_username(code, name)
            password = generate_password()
            db.users.insert_one({
                "username": username, "password": hash_password(password),
                "role": "department", "name": name, "dept_code": code,
                "active": True, "must_change": False, "created_at": now(),
            })
            db.departments.update_one({"dept_code": code},
                                      {"$set": {"username": username,
                                                "initial_password": password,
                                                "credentials_generated_at": now(),
                                                "credentials_generated_by": "devserver"}})
            print(f"  {username:12} {password:16} {name}")
        print(f"\n  admin: {app.config['ADMIN_USERNAME']} / {app.config['ADMIN_PASSWORD']}")
        print(f"  http://127.0.0.1:{port}\n")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
