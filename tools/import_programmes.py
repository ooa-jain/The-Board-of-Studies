"""
Turn the Office of Academics programme workbook into the catalogue the portal
prefills Department Information from.

    python tools/import_programmes.py Programmes_2026_OOA.xlsx

Writes app/data/programmes.json. Run it again whenever the workbook changes
and deploy the new file; departments that have not yet saved Department
Information pick the new list up, the rest keep what they confirmed.
"""

import json
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "programmes.json"

# Header text in the workbook → key in the catalogue
COLUMNS = {
    "Programme Code": "programme_code",
    "Year of Introduction": "year_introduced",
    "Independent and Grouped / Specialised": "category",
    "Degree": "degree",
    "Regular Programmes offered for AY 2026-27": "programme_name",
    "Minors": "minors",
    "Department": "department",
    "Faculty": "faculty",
    "School": "school",
    "Bengaluru Campus Location": "location",
    "Kochi Campus": "kochi",
}


def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = " ".join(str(v).split())
    return "" if s == "-" else s


def main(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = [clean(h) for h in next(rows)]
    index = {COLUMNS[h]: i for i, h in enumerate(header) if h in COLUMNS}
    missing = set(COLUMNS.values()) - set(index)
    if missing:
        sys.exit(f"workbook is missing columns: {', '.join(sorted(missing))}")

    out = []
    for r in rows:
        rec = {k: clean(r[i]) if i < len(r) else "" for k, i in index.items()}
        if not rec["programme_code"] or not rec["programme_name"]:
            continue
        rec["kochi"] = rec["kochi"].lower() == "yes"
        out.append(rec)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} programmes to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
