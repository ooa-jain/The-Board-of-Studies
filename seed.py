"""
Seed the department master from the Office of Academics workbook.

    python seed.py            # add departments that do not already exist
    python seed.py --logins   # also issue a login for every department that
                              # has none, and print the list
    python seed.py --wipe     # clear departments, users (except admin) and
                              # submissions first, then seed

Faculty, school, department, place and campus come from the Office of
Academics workbook. Nothing about a person does: the portal holds no
director, dean or HoD details, because a department files here, not an
individual.

A department that teaches at more than one campus is more than one record:
each campus files its own Board of Studies record, so each needs its own
login. The code is what a submission hangs off, so it has to stay unique and
stable.
"""

import sys

from app import create_app
from app.db import get_db, issue_department_login, now

# (Faculty, School, Department, Place, Campus, Code)
SEED_DEPARTMENTS = [

    # Faculty of Engineering and Technology
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Computer Science and Engineering",
     "Bangalore", "Jain Global Campus", "CSE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Computer Science and Engineering",
     "Bangalore", "Jayanagar Campus", "CSE-JYN"),
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Computer Science and Engineering",
     "Kochi", "Kochi Campus", "CSE-KCH"),
    ("Faculty of Engineering and Technology",
     "School of Computer Science and Engineering",
     "Department of Information Science and Engineering",
     "Bangalore", "Jain Global Campus", "ISE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Aerospace Engineering",
     "Department of Aerospace Engineering",
     "Bangalore", "Jain Global Campus", "AE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Civil Engineering",
     "Bangalore", "Jain Global Campus", "CE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Mechanical Engineering",
     "Bangalore", "Jain Global Campus", "ME-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Electrical and Electronics Engineering",
     "Bangalore", "Jain Global Campus", "EEE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Electronics and Communication Engineering",
     "Bangalore", "Jain Global Campus", "ECE-JGC"),
    ("Faculty of Engineering and Technology",
     "School of Engineering & Technology",
     "Department of Food Technology",
     "Bangalore", "Jain Global Campus", "FT-JGC"),

    # Faculty of Arts, Humanities and Social Sciences
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Humanities & Social Sciences",
     "Bangalore", "Jayanagar Campus", "HSS-JYN"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Humanities & Social Sciences",
     "Bangalore", "Lalbagh Campus (Jainology)", "HSS-LBJ"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Humanities & Social Sciences",
     "Kochi", "Kochi Campus", "HSS-KCH"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Economics",
     "Bangalore", "Jayanagar Campus", "ECON-JYN"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Economics",
     "Kochi", "Kochi Campus", "ECON-KCH"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Performing Arts and Cultural Studies",
     "Bangalore", "JP Nagar Campus", "PACS-JPN"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Languages",
     "Bangalore", "Jayanagar Campus", "LANG-JYN"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Languages",
     "Kochi", "Kochi Campus", "LANG-KCH"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Journalism and Mass Communication",
     "Bangalore", "Lalbagh Campus", "JMC-LBG"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Humanities and Social Sciences",
     "Department of Journalism and Mass Communication",
     "Kochi", "Kochi Campus", "JMC-KCH"),
    ("Faculty of Arts, Humanities and Social Sciences",
     "School of Law",
     "Department of Law",
     "Bangalore", "Sheshadri Road Campus", "LAW-SHR"),

    # Faculty of Basic and Applied Sciences
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Chemistry and Biochemistry",
     "Bangalore", "JC Road Campus", "CB-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Chemistry and Biochemistry",
     "Bangalore", "Jain Global Campus", "CB-JGC"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Chemistry and Biochemistry",
     "Kochi", "Kochi Campus", "CB-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Biotechnology and Genetics",
     "Bangalore", "JC Road Campus", "BG-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Biotechnology and Genetics",
     "Kochi", "Kochi Campus", "BG-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Microbiology and Botany",
     "Bangalore", "JC Road Campus", "MB-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Data Analytics and Mathematical Science",
     "Bangalore", "JC Road Campus", "DAMS-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Data Analytics and Mathematical Science",
     "Kochi", "Kochi Campus", "DAMS-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Forensic Science",
     "Bangalore", "JC Road Campus", "FS-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Forensic Science",
     "Kochi", "Kochi Campus", "FS-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Physics and Electronics",
     "Bangalore", "JC Road Campus", "PE-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Psychology and Allied Sciences",
     "Bangalore", "JC Road Campus", "PAS-JCR"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sciences",
     "Department of Psychology and Allied Sciences",
     "Kochi", "Kochi Campus", "PAS-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Allied Healthcare and Sciences",
     "Department of Allied Healthcare and Sciences",
     "Bangalore", "Whitefield Campus", "AHS-WHF"),
    ("Faculty of Basic and Applied Sciences",
     "School of Allied Healthcare and Sciences",
     "Department of Allied Healthcare and Sciences",
     "Kochi", "Kochi Campus", "AHS-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Sports Science & Research",
     "Department of Allied Healthcare and Sciences",
     "Bangalore", "The Sports School", "AHS-TSS"),
    ("Faculty of Basic and Applied Sciences",
     "School of Computer Science & Information Technology",
     "Department of Computer Science and IT",
     "Bangalore", "Jayanagar Campus", "CSI-JYN"),
    ("Faculty of Basic and Applied Sciences",
     "School of Computer Science & Information Technology",
     "Department of Computer Science and IT",
     "Kochi", "Kochi Campus", "CSI-KCH"),
    ("Faculty of Basic and Applied Sciences",
     "School of Computer Science & Information Technology",
     "Department of Animation and Virtual Reality",
     "Bangalore", "Jayanagar Campus", "AVR-JYN"),

    # Faculty of Commerce
    ("Faculty of Commerce",
     "School of Commerce",
     "Department of Commerce",
     "Bangalore", "Jayanagar Campus", "COMM-JYN"),
    ("Faculty of Commerce",
     "School of Commerce",
     "Department of Commerce",
     "Kochi", "Kochi Campus", "COMM-KCH"),

    # Faculty of Management Studies
    ("Faculty of Management Studies",
     "CMS Business School",
     "Department of Management Studies",
     "Bangalore", "Sheshadri Road Campus", "MS-CBS-SHR"),
    ("Faculty of Management Studies",
     "CMS Business School",
     "Department of Management Studies",
     "Bangalore", "Lalbagh Campus", "MS-LBG"),
    ("Faculty of Management Studies",
     "CMS Business School",
     "Department of Management Studies",
     "Bangalore", "Jayanagar Campus", "MS-CBS-JYN"),
    ("Faculty of Management Studies",
     "CMS Business School",
     "Department of Management Studies",
     "Kochi", "Kochi Campus", "MS-KCH"),
    ("Faculty of Management Studies",
     "School of Aviation and Aerospace Management",
     "Department of Management Studies",
     "Bangalore", "Jayanagar Campus", "MS-SAA-JYN"),
    ("Faculty of Management Studies",
     "School of Aviation and Aerospace Management",
     "Department of Management Studies",
     "Bangalore", "Sheshadri Road Campus", "MS-SAA-SHR"),

    # Faculty of Creativity and Design
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Design",
     "Bangalore", "Yelahanka Campus", "DESI-YLH"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Design",
     "Kochi", "Kochi Campus", "DESI-KCH"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Art and Design",
     "Bangalore", "Yelahanka Campus", "AD-YLH"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Department of Art and Design",
     "Kochi", "Kochi Campus", "AD-KCH"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "Jainology",
     "Kochi", "Kochi Campus", "JAIN-KCH"),
    ("Faculty of Creativity and Design",
     "School of Design, Media and Creative Arts",
     "CeRSee",
     "Kochi", "Kochi Campus", "CERS-KCH"),
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

        added = updated = skipped = 0

        for faculty, school, name, place, campus, code in SEED_DEPARTMENTS:
            fields = {"faculty": faculty, "school": school, "dept_name": name,
                      "place": place, "campus": campus}
            existing = db.departments.find_one({"dept_code": code})
            if existing:
                # keep the department, but bring it up to date with the sheet
                if any(existing.get(k) != v for k, v in fields.items()):
                    db.departments.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {**fields, "updated_at": now()}})
                    updated += 1
                else:
                    skipped += 1
                continue

            db.departments.insert_one({
                "dept_code": code, **fields,
                "active": True, "created_at": now(), "updated_at": now(),
            })
            added += 1

        print(f"added {added} department(s)"
              + (f", updated {updated}" if updated else "")
              + (f", unchanged {skipped}" if skipped else ""))

        # Logins are issued for every department that has none — there is no
        # clicking through them one at a time.
        if "--logins" in sys.argv:
            issued = 0
            for dept in db.departments.find({"username": {"$exists": False}}
                                            ).sort("dept_code", 1):
                username, password = issue_department_login(db, dept, actor="seed")
                print(f"  {dept['dept_code']:10} {username:22} {password}")
                issued += 1
            if issued:
                print(f"\nissued {issued} login(s). These passwords are shown "
                      f"once; Admin \u2192 Departments \u2192 Credential sheet "
                      f"has them until each department signs in.")
            else:
                print("every department already has a login")


if __name__ == "__main__":
    main()
