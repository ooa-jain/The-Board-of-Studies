"""
Seed the department master.

    python seed.py            # add departments that do not already exist
    python seed.py --logins   # also generate a login for each, and print it
    python seed.py --wipe     # clear departments, users (except admin) and
                              # submissions first, then seed

Codes are what the login is derived from, so they have to stay unique and
stable — changing a code later changes that department's username. The school
each department sits under is the one thing here that was inferred rather than
supplied; correct any of them in Admin → Departments → Edit, or fix the list
below and re-run with --wipe.
"""

import sys

from app import create_app
from app.db import get_db, issue_department_login, now

# (School / Faculty, Department, Code)
SEED_DEPARTMENTS = [
    # ---- Engineering and Technology ------------------------------------
    ("Faculty of Engineering and Technology",
     "Department of Computer Science and Engineering", "CSE"),
    ("Faculty of Engineering and Technology",
     "Department of Information Science and Engineering", "ISE"),
    ("Faculty of Engineering and Technology",
     "Department of Aerospace Engineering", "AER"),
    ("Faculty of Engineering and Technology",
     "Department of Civil Engineering", "CIV"),
    ("Faculty of Engineering and Technology",
     "Department of Mechanical Engineering", "MEC"),
    ("Faculty of Engineering and Technology",
     "Department of Electrical and Electronics Engineering", "EEE"),
    ("Faculty of Engineering and Technology",
     "Department of Electronics and Communication Engineering", "ECE"),
    ("Faculty of Engineering and Technology",
     "Department of Food Technology", "FDT"),

    # ---- Humanities, Social Sciences and Law ---------------------------
    ("School of Humanities and Social Sciences",
     "Department of Humanities & Social Sciences", "HSS"),
    ("School of Humanities and Social Sciences",
     "Department of Economics", "ECO"),
    ("School of Humanities and Social Sciences",
     "Department of Performing Arts and Cultural Studies", "PAC"),
    ("School of Humanities and Social Sciences",
     "Department of Languages", "LAN"),
    ("School of Humanities and Social Sciences",
     "Department of Journalism and Mass Communication", "JMC"),
    ("School of Law", "Department of Law", "LAW"),

    # ---- Sciences -------------------------------------------------------
    ("School of Sciences", "Department of Chemistry and Biochemistry", "CHB"),
    ("School of Sciences", "Department of Biotechnology and Genetics", "BTG"),
    ("School of Sciences", "Department of Microbiology and Botany", "MBB"),
    ("School of Sciences",
     "Department of Data Analytics and Mathematical Science", "DAM"),
    ("School of Sciences", "Department of Forensic Science", "FRS"),
    ("School of Sciences", "Department of Physics and Electronics", "PHE"),
    ("School of Sciences",
     "Department of Psychology and Allied Sciences", "PSY"),
    ("School of Sciences",
     "Department of Allied Healthcare and Sciences", "AHS"),

    # ---- Computer Science and IT ----------------------------------------
    ("School of Computer Science and IT",
     "Department of Computer Science and IT", "CSIT"),
    ("School of Computer Science and IT",
     "Department of Animation and Virtual Reality", "AVR"),

    # ---- Commerce and Management ----------------------------------------
    ("School of Commerce and Management", "Department of Commerce", "COM"),
    ("School of Commerce and Management",
     "Department of Management Studies", "MGT"),

    # ---- Design ----------------------------------------------------------
    ("School of Design", "Department of Design", "DSN"),
    ("School of Design", "Department of Art and Design", "ARD"),

    # ---- Centres ---------------------------------------------------------
    ("Centres", "Jainology", "JNL"),
    ("Centres", "CeRSee", "CERSEE"),
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
        added = skipped = 0

        for school, name, code in SEED_DEPARTMENTS:
            if db.departments.find_one({"dept_code": code}):
                skipped += 1
                continue
            db.departments.insert_one({
                "dept_code": code, "dept_name": name, "school": school,
                "campus": app.config["CAMPUSES"][0],
                "active": True, "created_at": now(), "updated_at": now(),
            })
            added += 1

            if made_logins:
                dept = db.departments.find_one({"dept_code": code})
                # the same path the admin screens use, so a seeded login and a
                # generated one are identical
                username, password = issue_department_login(db, dept, actor="seed")
                print(f"  {code:8} {username:24} {password}")

        print(f"added {added} department(s)"
              + (f", skipped {skipped} already present" if skipped else ""))
        if made_logins and added:
            print("\nThese passwords are shown once. Admin → Departments → "
                  "Credential sheet has them until each department signs in.")


if __name__ == "__main__":
    main()
