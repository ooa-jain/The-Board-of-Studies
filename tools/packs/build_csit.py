"""
Build the Department of Computer Science and IT data pack (app/pack_data/csit.json).

Source: the department's Google Drive folder
  https://drive.google.com/drive/folders/1cUc3G3BF6GdPdsM4twOU3ekKI3BThYqF

The five MCA course matrices and the BCA minor buckets are transcribed below
from the .xlsx files in that folder. The syllabi are parsed from the text
export of each syllabus .docx:

    python tools/packs/build_csit.py <folder with gen.txt sct.txt isms.txt cs.txt genai.txt>

Every place the import departs from the source file is listed in NOTES, and
the admin sees those notes on the department's record.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_syllabus as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app" / "pack_data" / "csit.json"

FOLDER = "https://drive.google.com/drive/folders/1cUc3G3BF6GdPdsM4twOU3ekKI3BThYqF"

CATEGORY = {
    "CC": "Major (Core)",
    "DSE": "Discipline Specific Elective (DSE)",
    "OE": "Multidisciplinary",
    "SEC": "Skill Enhancement Courses (SEC)",
    "INT": "Summer Internship",
    "PRJ": "Research Project / Dissertation",
}

# (semester, code, title, category, L, T, P, E, CA %, ESE %, credits)
# CA / ESE are the percentage weightages printed in the matrix; "NA" is 0.

SEM1 = [
    (1, "25MCAC101", "Data Structures & Algorithms", "CC", 3, 0, 0, 0, 50, 50, 3),
    (1, "25MCAC102", "Advanced Computer Networks", "CC", 3, 0, 0, 0, 50, 50, 3),
    (1, "25MCAC103", "Python Programming", "CC", 3, 0, 0, 0, 70, 30, 3),
    (1, "25MCAC104", "Artificial Intelligence", "CC", 3, 0, 0, 0, 50, 50, 3),
    (1, "25MCAC105", "Mathematical Foundation For Computer Applications", "CC", 3, 0, 0, 0, 50, 50, 3),
    (1, "25CSPGET11", "Employability Skill Training-1 (Vedic Mathematics and Competitive Coding)",
     "SEC", 1, 0, 2, 0, 100, 0, 2),
    (1, "TBA-OE-S1", "Open Elective Course", "OE", 3, 0, 0, 0, 50, 50, 3),
    (1, "25MCAC101L", "Data Structures & Algorithms Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
    (1, "25MCAC102L", "Advanced Computer Networks Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
    (1, "25MCAC103L", "Python Programming Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
]


def sem2(dse, dse_title, rm_category="CC", dse_ca=60, dse_ese=40):
    return [
        (2, "25MCAC201", "Object Oriented Programming Using Java", "CC", 2, 0, 0, 3, 70, 30, 3),
        (2, "25MCAC202", "Database Technologies", "CC", 3, 0, 0, 0, 70, 30, 3),
        (2, "25MCAC203", "Machine Learning (Integrated with Swayam Course)", "CC", 3, 0, 0, 0, 60, 40, 3),
        (2, " / ".join(dse), " / ".join(dse_title), "DSE", 2, 0, 0, 3, dse_ca, dse_ese, 3),
        (2, "25CSPGET21",
         "Employability Skill Training-2 (Quantitative Aptitude and Competetive Coding)",
         "SEC", 1, 0, 2, 0, 100, 0, 2),
        (2, "25MCAC201L", "Object Oriented Programming Using Java Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
        (2, "25MCAC202L", "Database Technologies Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
        (2, "25MCAC203L", "Machine Learning Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
        (2, " / ".join(c + "L" for c in dse), " / ".join(t + " Lab" for t in dse_title),
         "DSE", 0, 0, 2, 0, 100, 0, 1),
        (2, "TBA-PCL-S2", "Trans Disciplinary Project Centric Learning-1 (TD-PCL-1)",
         "SEC", 0, 0, 0, 9, 50, 50, 3),
        (2, "25MCACRM1", "Research Methodology", rm_category, 0, 1, 0, 3, 100, 0, 2),
    ]


def sem3(core, dse, dse_title, internship, est="25CSPGET31"):
    rows = [(3, code, title, "CC", l, 0, 0, e, 60, 40, 3) for code, title, l, e in core]
    rows += [
        (3, " / ".join(dse), " / ".join(dse_title), "DSE", 3, 0, 0, 0, 60, 40, 3),
        (3, "TBA-OE-S3", "Open Elective", "OE", 3, 0, 0, 0, 50, 50, 3),
        (3, est, "Employability Skill Training-3 (Quantitative Aptitude and Competetive Coding)",
         "SEC", 1, 0, 2, 0, 100, 0, 2),
    ]
    rows += [(3, code + "L", title + " Lab", "CC", 0, 0, 2, 0, 100, 0, 1) for code, title, _, _ in core]
    rows.append((3, internship, "Summer Internship / Capstone project", "INT", 0, 0, 0, 9, 100, 0, 3))
    return rows


def sem4(e2, e2_title, e3, e3_title):
    return [
        (4, "25MCACE4011 / 25MCACE4012",
         "Professional Ethics and Values (Integrated with Swayam Course) / IT Governance and Ethics",
         "DSE", 2, 0, 0, 3, 60, 40, 3),
        (4, " / ".join(e2), " / ".join(e2_title), "DSE", 2, 0, 0, 3, 50, 50, 3),
        (4, " / ".join(e3), " / ".join(e3_title), "DSE", 3, 0, 0, 0, 50, 50, 3),
        (4, "TBA-PRJ-S4", "Project / Internship", "PRJ", 2, 0, 4, 15, 50, 50, 9),
        (4, "TBA-PCL-S4", "Trans Disciplinary Project Centric Learning-2 (TD-PCL-2)",
         "SEC", 0, 0, 0, 9, 50, 50, 3),
    ]


MCA_COMMON = {"degree_level": "PG - 2 Year"}

PROGRAMMES = [
    {
        "programme_code": "MCAREG", "programme_name": "Master of Computer Applications",
        "specialisation": "General", "syllabus": "gen",
        "drive": ["2026-2028_MCA GEN_Course MAtrix.xlsx", "MCA_GEN_SYLLABUS_2026_28.docx"],
        "structure": SEM1
        + sem2(["25MCAGE2041", "25MCAGE2042"],
               ["Essentials of Cloud Computing", "Essentials of Cyber Security"])
        + sem3([("25MCAG301", "NoSQL Databases", 2, 3), ("25MCAG302", "Internet of Things", 2, 3),
                ("25MCAG303", "Mobile Application Development", 3, 0)],
               ["25MCAGE3041", "25MCAGE3042"], ["Data Science", "Software Engineering"],
               "25MCAG304SI / 25MCAG304CP", est="25CSPGET31 / 25CSPGEP31")
        + sem4(["25MCAGE4021", "25MCAGE4022"],
               ["Natural Language Processing", "Software Quality Assurance and Testing"],
               ["25MCAGE4031", "25MCAGE4032"],
               ["Software Project Management", "Essentials of Blockchain"]),
    },
    {
        "programme_code": "MCACYS",
        "programme_name": "Master of Computer Applications (with specialisation in Cyber Security)",
        "specialisation": "Cyber Security", "syllabus": "cs",
        "drive": ["2026-2028_MCA_CS_Course Matrix.xlsx", "MCA CS_SYLLABUS_2026_28.doc"],
        "structure": [
            (1, "25MCAC101", "Data Structures & Algorithms", "CC", 3, 0, 0, 0, 50, 50, 3),
            (1, "25MCAC102", "Advanced Computer Networks", "CC", 3, 0, 0, 0, 50, 50, 3),
            (1, "25MCAC103", "Python Programming", "CC", 3, 0, 0, 0, 70, 30, 3),
            (1, "25MCAC104", "Artificial Intelligence", "CC", 2, 0, 0, 3, 50, 50, 3),
            (1, "25MCAC105", "Mathematical Foundation For Computer Applications", "CC",
             3, 0, 0, 0, 50, 50, 3),
            (1, "25CSPGET11 / 25CSPGEP11",
             "Employability Skill Training-1 (Vedic Mathematics and Competitive Coding) / "
             "Entrepreneurship - 1", "SEC", 1, 0, 0, 3, 100, 0, 2),
            (1, "TBA-OE-S1", "Open Elective Course-1", "OE", 3, 0, 0, 0, 50, 50, 3),
            (1, "25MCAC101L", "Data Structures & Algorithms Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (1, "25MCAC102L", "Advanced Computer Networks Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (1, "25MCAC103L", "Python Programming Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (2, "25MCAC201", "Object Oriented Programming Using Java", "CC", 2, 0, 0, 3, 70, 30, 3),
            (2, "25MCAC202", "Database Technologies", "CC", 3, 0, 0, 0, 70, 30, 3),
            (2, "25MCAC203", "Machine Learning (Integrated with Swayam Course)", "CC",
             3, 0, 0, 0, 60, 40, 3),
            (2, "25MCACSE2041 / 25MCACSE2042", "Ethical Hacking / Network Security", "DSE",
             2, 0, 0, 3, 60, 40, 3),
            (2, "25CSPGET21 / 25CSPGEP21",
             "Employability Skill Training-2 (Quantitative Aptitude and Competetive Coding) / "
             "Entrepreneurship - 2", "SEC", 1, 0, 0, 3, 100, 0, 2),
            (2, "25MCAC201L", "Object Oriented Programming Using Java Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (2, "25MCAC202L", "Database Technologies Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (2, "25MCAC203L", "Machine Learning Lab for CyberSecurity", "CC", 0, 0, 2, 0, 100, 0, 1),
            (2, "25MCACSE2041L / 25MCACSE2042L", "Ethical Hacking Lab / Network Security Lab", "DSE",
             0, 0, 2, 0, 100, 0, 1),
            (2, "TBA-PCL-S2", "Trans Disciplinary Project Centric Learning-1 (TD-PCL-1)", "SEC",
             0, 1, 0, 6, 50, 50, 3),
            (2, "25MCACRM1", "Research Methodology", "CC", 0, 1, 0, 3, 100, 0, 2),
            (3, "25MCACS301", "Cyber Forensics", "CC", 2, 0, 0, 3, 60, 40, 3),
            (3, "25MCACS302", "Applied Cryptography", "CC", 2, 0, 0, 3, 60, 40, 3),
            (3, "25MCACS303", "Blockchain Technologies", "CC", 3, 0, 0, 0, 60, 40, 3),
            (3, "25MCACSE3041 / 25MCACSE3042", "Secure Software Development / Web Application Security",
             "DSE", 3, 0, 0, 0, 60, 40, 3),
            (3, "TBA-OE-S3", "Open Elective", "OE", 3, 0, 0, 0, 50, 50, 3),
            (3, "25CSPGET31 / 25CSPGEP31",
             "Employability Skill Training-3 (Quantitative Aptitude and Competetive Coding) / "
             "Entrepreneurship - 3", "SEC", 1, 0, 0, 3, 100, 0, 2),
            (3, "25MCACS301L", "Cyber Forensics Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (3, "25MCACS302L", "Applied Cryptography Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (3, "25MCACS303L", "Blockchain Technologies Lab", "CC", 0, 0, 2, 0, 100, 0, 1),
            (3, "25MCACS304SI / 25MCACS304CP", "Summer Internship / Capstone project", "INT",
             0, 0, 0, 9, 100, 0, 3),
            (4, "25MCACE4011 / 25MCACE4012",
             "Professional Ethics and Values (Integrated with Swayam Course) / IT Governance and Ethics",
             "DSE", 2, 0, 0, 3, 60, 40, 3),
            (4, "25MCACSE4021 / 25MCACSE4022", "IoT Security / Virtualization and Cloud Security", "DSE",
             2, 0, 0, 3, 50, 50, 3),
            (4, "25MCACSE4031 / 25MCACSE4032",
             "Cyber Threat Intelligence / Security Operation Centre Management", "DSE",
             3, 0, 0, 0, 50, 50, 3),
            (4, "25MCACS404 / 25MCACS405", "Project / Internship", "PRJ", 2, 0, 4, 15, 50, 50, 9),
            (4, "TBA-PCL-S4", "Trans Disciplinary Project Centric Learning-2 (TD-PCL-2)", "SEC",
             0, 1, 0, 6, 50, 50, 3),
        ],
    },
    {
        "programme_code": "MCASCT",
        "programme_name": "Master of Computer Applications (with specialisation in Storage and "
                          "Cloud Technology)",
        "specialisation": "Storage and Cloud Technology", "syllabus": "sct",
        "drive": ["2026-2028_MCA SCT_Course Matrix.xlsx", "MCA_SCT_SYLLABUS_2026_28.docx"],
        "structure": SEM1
        + sem2(["25MCASCE2041", "25MCASCE2042"],
               ["Cloud Web Services", "Cloud Computing and Virtualization"], rm_category="SEC")
        + sem3([("25MCASC301", "Advanced Cloud Web Services", 2, 3),
                ("25MCASC302", "Cloud Analytics", 2, 3),
                ("25MCASC303", "Machine Learning in Cloud Computing", 3, 0)],
               ["25MCASCE3041", "25MCASCE3042"],
               ["Programming for Cloud Platform", "Datacenter Virtualization"],
               "25MCAIS304SI / 25MCAIS304CP")
        + sem4(["25MCASCE4021", "25MCASCE4022"], ["DevOps", "Containers and Microservices"],
               ["25MCASCE4031", "25MCASCE4032"],
               ["Cloud Security and Compliance", "OpenStack in Cloud Computing"]),
    },
    {
        "programme_code": "MCAISM",
        "programme_name": "Master of Computer Applications (with specialisation in Information "
                          "Security Management Services)",
        "specialisation": "Information Security Management Services", "syllabus": "isms",
        "drive": ["2026-2028_MCA ISMS_Course Matrix.xlsx", "MCA_ISMS_SYLLABUS_2026_28.docx"],
        "structure": SEM1
        + sem2(["25MCAISE2041", "25MCAISE2042"], ["Ethical Hacking", "Network Security"])
        + sem3([("25MCAIS301", "Incident Response and Cyber Forensics", 2, 3),
                ("25MCAIS302", "Machine Learning for Cyber Security", 2, 3),
                ("25MCAIS303", "Blockchain Technologies", 3, 0)],
               ["25MCAISE3041", "25MCAISE3042"],
               ["Security Auditing and Compliance", "Secure Communication Protocols"],
               "25MCAIS304SI / 25MCAIS304CP")
        + sem4(["25MCAISE4021", "25MCAISE4022"],
               ["Human Factors in Cybersecurity", "Cloud and Infrastructure Security"],
               ["25MCAISE4031", "25MCAISE4032"], ["Applied Cryptography", "Cyber Law"]),
    },
    {
        "programme_code": "MCAIML",
        "programme_name": "Master of Computer Applications (with specialisation in Artificial "
                          "Intelligence and Machine Learning)",
        "specialisation": "Artificial Intelligence and Machine Learning", "syllabus": None,
        "drive": ["2026-2028_MCA AIML_Course Matrix.xlsx"],
        "structure": SEM1
        + sem2(["25MCAAIE2041", "25MCAAIE2042"],
               ["Advanced Probability and Statistics", "Computer Vision"])
        + sem3([("25MCAAI301", "Deep Learning", 2, 3),
                ("25MCAAI302", "Predictive Analytics and Data Visualization", 2, 3),
                ("25MCAAI303", "Natural Language Processing", 3, 0)],
               ["25MCAAIE3041", "25MCAAIE3042"], ["Internet of Things", "Big Data Analytics"],
               "25MCAAI304SI / 25MCAAI304CP", est="25CSPGET31 / 25CSPGEP31")
        + sem4(["25MCAAIE4021", "25MCAAIE4022"], ["Digital Image Processing", "Biometrics"],
               ["25MCAAIE4031", "25MCAAIE4032"], ["MLOps", "Reinforcement Machine Learning"]),
    },
]

BCA = {
    "programme_code": "BCAGAI",
    "programme_name": "Bachelor of Computer Applications (Honours / Honours with Research) with "
                      "specialisation in Generative Artificial Intelligence",
    "degree_level": "UG - 4 Year (Honours with Research)", "specialisation": "Generative AI",
    "syllabus": "genai",
    "drive": ["2026 Minor Buckets-Course Matrix.xlsx", "GEN AI SYLLABUS 2026-2027.docx"],
}

# 2026 Minor Buckets-Course Matrix.xlsx — (minor, [(semester, code, title)])
MINORS = [
    ("Information Technology for Healthcare (ITH)", [
        (3, "26BCAIH3MR01", "Introduction to Healthcare Data and Analytics"),
        (4, "26BCAIH4MR01", "Applied Bio Statistics"),
        (4, "26BCAIH4MR01L", "Applied Bio Statistics Lab"),
        (4, "26BCAIH4MR02", "Artificial Intelligence for Healthcare"),
        (4, "26BCAIH4MR02L", "Artificial Intelligence for Healthcare Lab"),
        (5, "26BCAIH5MR01", "Machine Learning for Healthcare"),
        (5, "26BCAIH5MR02", "Data Visualization in Health Care"),
        (6, "26BCAIH6MR01", "Telehealth and Clinical Informatics"),
        (7, "26BCAIH7MR01", "Deep Learning and Imaging Analytics"),
        (8, "26BCAIH8MR01", "Standards, Ethics, and Regulation in Digital Health"),
    ]),
    ("Internet of Things (IoT)", [
        (3, "26BCAOT3MR01", "Basics Electronics"),
        (4, "26BCAOT4MR01", "Introduction to IOT"),
        (4, "26BCAOT4MR01L", "Introduction to IOT Lab"),
        (4, "26BCAOT4MR02", "Programming Languages for IoT"),
        (4, "26BCAOT4MR02L", "Programming Languages for IoT Lab"),
        (5, "26BCAOT5MR01", "Embedded System Design (PNT)"),
        (5, "26BCAOT5MR02", "5G and IoT Technologies"),
        (6, "26BCAIH6MR01", "Edge Computing"),
        (7, "26BCAOT7MR01", "Computer Vision and Robotics (PNT)"),
        (8, "26BCAOT8MR01", "IoT Automation (PNT)"),
    ]),
    ("AI for Rural Transformations (AIRT)", [
        (3, "26BCART3MR01", "Introduction to AI and Digital Transformation for Rural Development"),
        (4, "26BCART4MR01", "Data Analytics in Rural Contexts"),
        (4, "26BCART4MR01L", "Data Analytics in Rural Contexts Lab"),
        (4, "26BCART4MR02", "AI and Machine Learning"),
        (4, "26BCART4MR02L", "AI and Machine Learning Lab"),
        (5, "26BCART5MR01", "AI for Agriculture & Natural Resources"),
        (5, "26BCART5MR02", "Rural Health Informatics and e Health Systems"),
        (6, "26BCART6MR01", "5G and IoT Technologies"),
        (7, "26BCART7MR01", "Ethics, Policy & Sustainability in Rural AI"),
        (8, "26BCART8MR01", "AI Project / Field Deployment for Rural Area"),
    ]),
    ("Information Security", [
        (3, "26BCAIS3MR01", "Introduction to Information Security"),
        (4, "26BCAIS4MR01", "Network Security Fundamentals"),
        (4, "26BCAIS4MR01L", "Network Security Fundamentals Lab"),
        (4, "26BCAIS4MR02", "Cryptography and Data Protection"),
        (4, "26BCAIS4MR02L", "Cryptography and Data Protection Lab"),
        (5, "26BCAIS5MR01", "Ethical Hacking and Penetration Testing"),
        (5, "26BCAIS5MR02", "Digital Forensics and Incident Response"),
        (6, "26BCAIS6MR01", "Cloud and Application Security"),
        (7, "26BCAIS7MR01", "Cyber Risk Management and Incident handling"),
        (8, "26BCAIS8MR01", "Emerging Trends in Cybersecurity (AI, IoT, Quantum)"),
    ]),
    ("Cloud Computing", [
        (3, "26BCACC3MR01", "Fundamentals of Cloud Computing"),
        (4, "26BCACC4MR01", "Virtualization and Containerization"),
        (4, "26BCACC4MR01L", "Virtualization and Containerization Lab"),
        (4, "26BCACC4MR02", "Cloud Networking and Security"),
        (4, "26BCACC4MR02L", "Cloud Networking and Security Lab"),
        (5, "26BCACC5MR01", "Cloud Infrastructure Management"),
        (5, "26BCACC5MR02", "DevOps and Cloud Automation"),
        (6, "26BCACC6MR01", "Cloud Databases and Big Data Services"),
        (7, "26BCACC7MR01", "Serverless and Edge Computing"),
        (8, "26BCACC8MR01", "Cloud Application Development (Project Based)"),
    ]),
    ("Software Engineering", [
        (3, "26BCASE3MR01", "Fundamentals of Software Engineering (includes Object-Oriented Analysis "
                            "and Design, Software Requirements Engineering)"),
        (4, "26BCASE4MR01", "Java Spring Boot Development"),
        (4, "26BCASE4MR01L", "Java Spring Boot Development Lab"),
        (4, "26BCASE4MR02", "Software Architecture and Design Patterns"),
        (4, "26BCAIH4MR02L", "Software Architecture and Design Patterns Lab"),
        (5, "26BCASE5MR01", "Software Testing and Quality Management"),
        (5, "26BCASE5MR02", "Advanced JavaScript and Frontend Development Tools"),
        (6, "26BCASE6MR01", "Software Project Management"),
        (7, "26BCASE7MR01", "Agile Software Development and DevOps"),
        (8, "26BCASE8MR01", "Software Engineering Capstone Project"),
    ]),
    ("Data Science", [
        (3, "26BCADS3MR01", "Probability & Statistics for Data Science"),
        (4, "26BCADS4MR01", "Machine Learning"),
        (4, "26BCADS4MR01L", "Machine Learning Lab"),
        (4, "26BCADS4MR02", "Data Visualization (Tableau & Power BI)"),
        (4, "26BCADS4MR02L", "Data Visualization (Tableau & Power BI) Lab"),
        (5, "26BCADS5MR01", "Deep Learning"),
        (5, "26BCADS5MR02", "Cloud Computing for Data Science"),
        (6, "26BCADS6MR01", "Big Data Management"),
        (7, "26BCADS7MR01", "Natural Language Processing"),
        (8, "26BCADS8MR01", "Business Intelligence & Analytics"),
    ]),
    ("AI", [
        (3, "26BCAAI3MR01", "Introduction to AI & Machine Learning"),
        (4, "26BCAAI4MR01", "Advanced Machine Learning Techniques for Data Engineering"),
        (4, "26BCAAI4MR01L", "Advanced Machine Learning Techniques for Data Engineering Lab"),
        (4, "26BCAAI4MR02", "Python Programming for AI"),
        (4, "26BCAAI4MR02L", "Python Programming for AI Lab"),
        (5, "26BCAAI5MR01", "Natural Language Processing"),
        (5, "26BCAAI5MR02", "Data Visualization Tools and Techniques"),
        (6, "26BCAAI6MR01", "Deep Learning"),
        (7, "26BCAAI7MR01", "Generative AI and Large Language Models"),
        (8, "26BCAAI8MR01", "Explainable AI"),
    ]),
]

NOTES = [
    "Course codes starting with TBA- are placeholders: the matrices leave the code blank for the "
    "open electives, the Trans Disciplinary Project Centric Learning courses and the semester-4 "
    "Project / Internship. Replace them with the codes the university assigns.",
    "TD-PCL-1, TD-PCL-2 and Research Methodology are listed twice in the matrices — once with "
    "0 credits in the semester they start and once with their credits in the semester they "
    "finish. They are imported once, in the credited semester.",
    "Elective pairs are kept as one row with both codes and titles separated by “ / ”, as in the "
    "matrices. Each option gets its own syllabus.",
    "CA and ESE are imported as the percentage weightages printed in the matrices (out of 100); "
    "“NA” is imported as 0.",
    "MCACYS (Cyber Security): the course-code column of 2026-2028_MCA_CS_Course Matrix.xlsx is shifted against the "
    "titles in semesters I and III. Semester I–II core codes are taken from the other four MCA "
    "matrices (same titles); semester III codes follow the CS syllabus. 25MCACS302 / 25MCACS302L "
    "(Applied Cryptography), 25CSPGET11 / 25CSPGEP11, 25MCACRM1 and 25MCACS304SI / 25MCACS304CP "
    "are inferred from the numbering — confirm them.",
    "MCAISM (ISMS): semester II row 4 repeats the lab code “25MCAISE2041L / 25MCAISE2042L” for the "
    "theory electives; imported as 25MCAISE2041 / 25MCAISE2042 (Ethical Hacking / Network "
    "Security), matching the ISMS syllabus.",
    "MCASCT (Storage and Cloud Technology): the internship code “25MCAIS304SI / 25MCAIS304CP” is the ISMS code in the source "
    "matrix. Imported as written — confirm it.",
    "MCAREG and MCASCT: the semester-2 TD-PCL row is titled “Transdisciplinary Project Centric "
    "Learning 2” in the matrix; imported as TD-PCL-1 (the course started in semester 1).",
    "MCAIML (AIML): there is no AIML syllabus in the Drive folder. The courses AIML shares with "
    "MCA General (same code and title) take their syllabus from MCA_GEN_SYLLABUS_2026_28.docx; "
    "the AIML specialisation courses still need a syllabus.",
    "BCAGAI (BCA Generative AI): the folder has the minor buckets and the Generative AI syllabus, but no BCA course "
    "matrix. The minors are imported into Annexure I and the syllabi are imported without course "
    "codes; the programme structure still has to be entered. The degree level is set to "
    "UG - 4 Year (Honours with Research) from the eight-semester folder — change it if needed.",
    "BCA minors: 26BCAIH6MR01 (Edge Computing, IoT minor) and 26BCAIH4MR02L (Software "
    "Architecture lab) repeat Healthcare-minor codes in the source workbook. Imported as written.",
    "Course objectives are not part of the syllabus template, so they are not imported. Web "
    "references are added after the books, marked “Web:”.",
    "Not in the Drive folder, so not filled: which catalogue programmes the department runs this "
    "year (Department Information); the signed DIAC/DPAC documents; the BoS date and BoS "
    "documents; intake and eligibility for each programme; pedagogy and skill development "
    "activities in the syllabi; the Course Revision. The standard university wording fills "
    "selection procedure, medium, pattern, assessment, passing and award.",
]


def norm(s):
    s = (s or "").lower().replace("&", "and")
    s = re.sub(r"\(integrat[^)]*\)", "", s)
    s = re.sub(r"\b(lab|laboratory)\b", " lab ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def row(r):
    sem, code, title, cat, l, t, p, e, ca, ese, cr = r
    return {"semester": sem, "track": "All semesters", "nep_category": CATEGORY[cat],
            "course_code": code, "course_title": title, "l": l, "t": t, "p": p, "e": e,
            "credits": cr, "cia": ca, "ese": ese, "total_marks": ca + ese}


def options(r):
    """One (code, title) per elective option of a structure row."""
    codes = [c.strip() for c in r["course_code"].split("/")]
    titles = [t.strip() for t in r["course_title"].split(" / ")]
    if len(titles) != len(codes):
        titles = [r["course_title"]] * len(codes)
    return list(zip(codes, titles))


def sheet(doc, code, title, semester, credits, hours_per_week):
    """One course's syllabus sheet, as the portal's syllabus template holds it."""
    teaching = int(doc["contact_hours"]) if doc.get("contact_hours") else None
    modules = [dict(m) for m in doc["modules"]]
    for m in modules:
        if m["title"] == "List of experiments" and m["hours"] == "" and teaching:
            m["hours"] = teaching
    books = list(doc["books"]) + [f"Web: {w}" for w in doc["web"]]
    return {
        "course_code": code, "course_title": title, "semester": semester,
        "credits": credits, "hours_per_week": hours_per_week,
        "teaching_hours": teaching if teaching else (hours_per_week or 0) * 15 or None,
        "pedagogy": "", "outcomes": "\n".join(doc["outcomes"]), "modules": modules,
        "skill_activities": "", "books": "\n".join(books),
    }


def build_syllabus(structure, docs, codes_only=False):
    by_code = {d["code"].upper(): d for d in docs if d["code"]}
    by_title = {}
    for d in docs:
        by_title.setdefault(norm(d["title"]), d)
    out, used = [], set()
    for r in structure:
        for code, title in options(r):
            doc = by_code.get(code.upper())
            if codes_only:
                if doc is not None and norm(doc["title"]) != norm(title):
                    doc = None
            elif doc is None or norm(doc["title"]) != norm(title):
                doc = by_title.get(norm(title)) or doc
            if doc is None or id(doc) in used:
                continue
            used.add(id(doc))
            hours = sum(r[k] for k in ("l", "t", "p", "e"))
            out.append(sheet(doc, code, title, r["semester"], r["credits"], hours))
    return out


def split_heading(s):
    # "Technical Proficiency and Problem-SolvingDemonstrate ..." → "...: Demonstrate ..."
    return re.sub(r"(?<=[a-z])(?=[A-Z][a-z]+ )", ": ", s, count=1) if ": " not in s else s


def minor_credits(semester, code):
    # every bucket in the workbook: 4 in semesters 3 and 5-8, 3 + 1 lab in semester 4
    if code.endswith("L"):
        return 1
    return 3 if semester == 4 else 4


def main(src):
    src = Path(src)
    texts = {n: (src / f"{n}.txt").read_text() for n in ("gen", "sct", "isms", "cs", "genai")}
    docs = {n: P.parse(t) for n, t in texts.items()}
    peos = {n: [split_heading(x) for x in P.peos(t)] for n, t in texts.items()}

    packs = {}
    for p in PROGRAMMES:
        structure = [row(r) for r in p["structure"]]
        profile = {"objective": "\n".join(peos[p["syllabus"] or "gen"])}
        part = {"prog_curriculum": {
            "details": {"degree_level": MCA_COMMON["degree_level"],
                        "specialisation": p["specialisation"]},
            "profile": profile,
            "semester_structure": structure,
        }}
        if p["syllabus"]:
            courses = build_syllabus(structure, docs[p["syllabus"]])
        else:
            # no syllabus of its own: the courses it shares (same code) with MCA General
            courses = build_syllabus(structure, [d for d in docs["gen"] if d["code"]],
                                     codes_only=True)
        part["prog_syllabus"] = {"courses": courses}
        packs[p["programme_code"]] = {"programme_name": p["programme_name"], **part}
        total = sum(r["credits"] for r in structure)
        print(f"{p['programme_code']:8} {len(structure):3} courses {total:4} credits  "
              f"{len(courses)} syllabi")

    seen, genai = set(), []
    for d in docs["genai"]:
        key = norm(d["title"])
        if key in seen:
            continue
        seen.add(key)
        genai.append(sheet(d, "", d["title"], d["semester"],
                           int(d["credits"]) if d["credits"] else None, None))
    minors = [{"minor_title": minor, "semester": sem, "course_code": code,
               "course_title": title, "credits": minor_credits(sem, code)}
              for minor, rows in MINORS for sem, code, title in rows]
    packs[BCA["programme_code"]] = {
        "programme_name": BCA["programme_name"],
        "prog_curriculum": {
            "details": {"degree_level": BCA["degree_level"], "specialisation": BCA["specialisation"]},
            "profile": {"objective": "\n".join(peos["genai"])},
            "minors": minors,
        },
        "prog_syllabus": {"courses": genai},
    }
    print(f"{BCA['programme_code']:8} minors {len(minors)}  syllabi {len(genai)}")

    files = ["Checklist for Document Submission_Department of Computer Science and IT.xlsx"]
    for p in PROGRAMMES + [BCA]:
        files += p["drive"]

    pack = {
        "key": "csit",
        "title": "Department of Computer Science and IT — BoS 2026 Drive folder",
        "source": {"folder": FOLDER,
                   "folder_name": "Department of Computer Science and Information Technology",
                   "files": files},
        # matched to the department master by name; created only if it is not there
        "department": {"dept_code": "CSIT", "dept_name": "Department of Computer Science and IT",
                       "school": "School of Computer Science and IT",
                       "faculty": "Faculty of Applied Computing", "campus": "Jayanagar Campus"},
        "programmes": packs,
        "open_stages": ["curriculum"],
        "notes": NOTES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
