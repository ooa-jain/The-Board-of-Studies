"""
Seed the department master from the Office of Academics contact directory.

    python seed.py            # add departments that do not already exist
    python seed.py --logins   # also generate a login for each, and print it
    python seed.py --wipe     # clear departments, users (except admin) and
                              # submissions first, then seed

Faculty, school and department come from
"Contact Details - Directors, Dy. Directors, Deans, HoDs". Nothing about a
person does: the portal holds no director, dean or HoD details, because a
department files here, not an individual.

Codes are what the login derives from, so they have to stay unique and stable —
changing a code later changes that department's username.
"""

import sys

from app import create_app
from app.db import get_db, issue_department_login, now

# (Faculty, School, Department, Code)
SEED_DEPARTMENTS = [

    # Faculty of Engineering and Technology
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Computer Science and Engineering", "CSE"),
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Information Science and Engineering", "ISE"),
    ("Faculty of Engineering and Technology",
     "School of Aerospace Engineering",
     "Department of Aerospace Engineering", "AER"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Civil Engineering", "CIV"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Mechanical Engineering", "MEC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Electrical and Electronics Engineering", "EEE"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Electronics and Communication Engineering", "ECE"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Food Technology", "FDT"),

    # Faculty of Arts, Humanities and Social Sciences
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Humanities & Social Sciences", "HSS"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Economics", "ECO"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Performing Arts and Cultural Studies", "PAC"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Languages", "LAN"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Journalism and Mass Communication", "JMC"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Law",
     "Department of Law", "LAW"),

    # Faculty of Basic and Applied Sciences
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Chemistry and Biochemistry", "CHB"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Biotechnology and Genetics", "BTG"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Microbiology and Botany", "MBB"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Data Analytics and Mathematical Science", "DAM"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Forensic Science", "FRS"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Physics and Electronics", "PHE"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Psychology and Allied Sciences", "PSY"),
    ("Faculty of Basic and Applied Sciences",
     "School of Allied Healthcare and Sciences",
     "Department of Allied Healthcare and Sciences", "AHS"),
    ("Faculty of Basic and Applied Sciences",
     "School of Computer Science & Information Technology",
     "Department of Computer Science and IT", "CSIT"),
    ("Faculty of Basic and Applied Sciences",
     "School of Computer Science & Information Technology",
     "Department of Animation and Virtual Reality", "AVR"),

    # Faculty of Commerce
    ("Faculty of Commerce",
     "School of Commerce",
     "Department of Commerce", "COM"),

    # Faculty of Management Studies
    ("Faculty of Management Studies",
     "CMS Business School",
     "Department of Management Studies", "MGT"),

    # Faculty of Creativity and Design
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Design", "DSN"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Art and Design", "ARD"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Jainology", "JNL"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "CeRSee", "CERSEE"),
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
        added = updated = skipped = 0

        for faculty, school, name, code in SEED_DEPARTMENTS:
            existing = db.departments.find_one({"dept_code": code})
            if existing:
                # keep an existing department, but bring its faculty and school
                # up to date with the directory
                if (existing.get("faculty") != faculty
                        or existing.get("school") != school):
                    db.departments.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"faculty": faculty, "school": school,
                                  "updated_at": now()}})
                    updated += 1
                else:
                    skipped += 1
                continue

            db.departments.insert_one({
                "dept_code": code, "dept_name": name,
                "faculty": faculty, "school": school,
                "campus": app.config["CAMPUSES"][0],
                "active": True, "created_at": now(), "updated_at": now(),
            })
            added += 1

            if made_logins:
                dept = db.departments.find_one({"dept_code": code})
                username, password = issue_department_login(db, dept, actor="seed")
                print(f"  {code:8} {username:24} {password}")

        print(f"added {added} department(s)"
              + (f", updated {updated}" if updated else "")
              + (f", unchanged {skipped}" if skipped else ""))
        if made_logins and added:
            print("\nThese passwords are shown once. Admin -> Departments -> "
                  "Credential sheet has them until each department signs in.")


if __name__ == "__main__":
    main()
