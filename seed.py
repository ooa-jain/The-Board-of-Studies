"""
Seed the department master with a starter set, for demonstration or first run.

    python seed.py            # add departments that do not already exist
    python seed.py --logins   # also generate a login for each
    python seed.py --wipe     # clear departments, users (except admin) and submissions first

Replace SEED_DEPARTMENTS with the real list, or use
Admin → Departments → Import from Excel to load the contact directory workbook.
"""

import sys

from app import create_app
from app.db import (generate_password, get_db, hash_password, now,
                    slugify_username)

SEED_DEPARTMENTS = [
    # (School / Faculty, Department, Code, Campus)
    ("School of Commerce and Management", "Department of Commerce", "COM", "Bengaluru"),
    ("School of Commerce and Management", "Department of Management Studies", "MGT", "Bengaluru"),
    ("School of Commerce and Management", "Department of Business Administration", "BBA", "Bengaluru"),
    ("School of Sciences", "Department of Computer Science", "CSC", "Bengaluru"),
    ("School of Sciences", "Department of Mathematics", "MAT", "Bengaluru"),
    ("School of Sciences", "Department of Physics", "PHY", "Bengaluru"),
    ("School of Sciences", "Department of Chemistry", "CHE", "Bengaluru"),
    ("School of Sciences", "Department of Biotechnology", "BIO", "Bengaluru"),
    ("Faculty of Engineering and Technology", "Department of Computer Science and Engineering",
     "CSE", "Bengaluru"),
    ("Faculty of Engineering and Technology", "Department of Electronics and Communication",
     "ECE", "Bengaluru"),
    ("Faculty of Engineering and Technology", "Department of Mechanical Engineering",
     "MEC", "Bengaluru"),
    ("Faculty of Engineering and Technology", "Department of Civil Engineering", "CIV", "Bengaluru"),
    ("School of Humanities and Social Sciences", "Department of English", "ENG", "Bengaluru"),
    ("School of Humanities and Social Sciences", "Department of Psychology", "PSY", "Bengaluru"),
    ("School of Humanities and Social Sciences", "Department of Economics", "ECO", "Bengaluru"),
    ("School of Law", "Department of Law", "LAW", "Bengaluru"),
    ("School of Design", "Department of Design", "DSN", "Bengaluru"),
    ("School of Allied Healthcare and Sciences", "Department of Allied Health Sciences",
     "AHS", "Bengaluru"),
    ("School of Commerce and Management", "Department of Commerce", "COM-KC", "Kochi"),
    ("School of Commerce and Management", "Department of Management Studies", "MGT-KC", "Kochi"),
    ("School of Sciences", "Department of Computer Science", "CSC-KC", "Kochi"),
    ("School of Humanities and Social Sciences", "Department of English", "ENG-KC", "Kochi"),
]


def main():
    app = create_app()
    with app.app_context():
        db = get_db()

        if "--wipe" in sys.argv:
            db.departments.delete_many({})
            db.users.delete_many({"role": "department"})
            db.submissions.delete_many({})
            print("cleared departments, department users and submissions")

        made_logins = "--logins" in sys.argv
        added = 0
        for school, name, code, campus in SEED_DEPARTMENTS:
            if db.departments.find_one({"dept_code": code}):
                continue
            db.departments.insert_one({
                "dept_code": code, "dept_name": name, "school": school, "campus": campus,
                "hod_name": "", "hod_designation": "Head of the Department",
                "hod_email": "", "hod_phone": "",
                "active": True, "created_at": now(), "updated_at": now(),
            })
            added += 1

            if made_logins:
                username = slugify_username(code, name)
                password = generate_password()
                db.users.insert_one({
                    "username": username, "password": hash_password(password),
                    "role": "department", "name": name, "dept_code": code,
                    "active": True, "must_change": False, "created_at": now(),
                })
                db.departments.update_one(
                    {"dept_code": code},
                    {"$set": {"username": username, "initial_password": password,
                              "credentials_generated_at": now(),
                              "credentials_generated_by": "seed"}})
                print(f"  {code:8} {username:22} {password}")

        print(f"added {added} department(s)")


if __name__ == "__main__":
    main()
