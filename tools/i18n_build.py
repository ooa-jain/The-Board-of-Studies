"""Builds app/translations/<code>.json from a key list and a translation
table: keys.json (the English text, in order) and <code>.tsv (index, tab,
translation). Placeholders in a key ({n}, {year}, {code}, {name}) become
{1}, {2} … in the translation, by place; this checks each line has them all.

    python3 tools/i18n_build.py tools/i18n hi kn ta ml

To correct a wording, change its line in tools/i18n/<code>.tsv and run this again.
"""
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "translations"


def build(folder, code):
    keys = json.loads((folder / "keys.json").read_text(encoding="utf-8"))
    words, bad = {}, []
    for line in (folder / f"{code}.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        i, _, text = line.partition("\t")
        key = keys[int(i)]
        if not text.strip():
            continue
        need = len(re.findall(r"\{\w+\}", key))
        have = set(re.findall(r"\{(\d+)\}", text))
        if have != {str(k) for k in range(1, need + 1)}:
            bad.append((i, key, text))
            continue
        words[key] = text
    OUT.mkdir(exist_ok=True)
    (OUT / f"{code}.json").write_text(json.dumps(words, ensure_ascii=False, indent=0, sort_keys=True),
                                      encoding="utf-8")
    return len(words), bad


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    for code in sys.argv[2:]:
        n, bad = build(folder, code)
        print(code, n, "strings")
        for b in bad:
            print("  placeholder mismatch:", *b)
