"""
Server-side validation engine.

Nothing is trusted from the browser.  Every stage submission is re-validated
here against three layers:

  1. Field-level typing  — the `type`, `pattern`, `min`, `max`, `min_words`,
     `min_items` declarations in app/schema.py.
  2. Named rules         — the `rules` list on each section, dispatched to the
     RULES registry below.
  3. UGC Table 2         — the credit engine in app/ugc_rules.py.

Every issue is a dict:
    {level, section, row, field, message}
`level` is "error" (blocks submission) or "warning" (shown, does not block).
"""

from __future__ import annotations

import re
from datetime import date, datetime

from . import ugc_rules as U
from .schema import STAGE_BY_KEY

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

BLOOM_VERBS = {
    "remember", "recall", "define", "list", "identify", "name", "state", "describe",
    "understand", "explain", "summarise", "summarize", "interpret", "classify", "discuss",
    "apply", "demonstrate", "implement", "use", "solve", "compute", "execute", "illustrate",
    "analyse", "analyze", "differentiate", "compare", "examine", "investigate", "distinguish",
    "evaluate", "assess", "justify", "critique", "appraise", "judge", "recommend",
    "create", "design", "develop", "formulate", "construct", "compose", "build", "produce",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def issue(level, message, section=None, row=None, field=None):
    return {"level": level, "message": message, "section": section, "row": row, "field": field}


def err(message, **kw):
    return issue("error", message, **kw)


def warn(message, **kw):
    return issue("warning", message, **kw)


def _is_blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or v == []


def _num(v):
    if _is_blank(v):
        return None
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None and float(n).is_integer() else None


def _lines(v):
    if _is_blank(v):
        return []
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def _words(v):
    return len(str(v or "").split())


def _parse_date(v):
    if _is_blank(v):
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _label(fdef):
    return fdef.get("label") or fdef.get("name")


# ---------------------------------------------------------------------------
# Layer 1 — field typing
# ---------------------------------------------------------------------------

def validate_field(fdef, value, section_key=None, row=None):
    """Validate one value against one field definition."""
    out = []
    name = fdef.get("name")
    label = _label(fdef)
    ftype = fdef.get("type", "text")
    where = {"section": section_key, "row": row, "field": name}

    if ftype in ("readonly",):
        return out

    if _is_blank(value):
        if fdef.get("required") and not fdef.get("auto_index"):
            if ftype == "checkbox":
                out.append(err(f"{label} must be ticked.", **where))
            else:
                out.append(err(f"{label} is required.", **where))
        return out

    if ftype == "checkbox":
        if fdef.get("required") and value not in (True, "true", "on", 1, "1", "Yes"):
            out.append(err(f"{label} must be ticked.", **where))
        return out

    if ftype in ("integer", "number"):
        n = _num(value)
        if n is None:
            out.append(err(f"{label} must be a number. You typed “{value}”.", **where))
            return out
        if ftype == "integer" and not float(n).is_integer():
            out.append(err(f"{label} must be a whole number, not {value}.", **where))
            return out
        if fdef.get("min") is not None and n < fdef["min"]:
            out.append(err(f"{label} cannot be less than {fdef['min']}. You typed {value}.", **where))
        if fdef.get("max") is not None and n > fdef["max"]:
            out.append(err(f"{label} cannot be more than {fdef['max']}. You typed {value}.", **where))
        return out

    if ftype == "email":
        if not EMAIL_RE.match(str(value).strip()):
            out.append(err(f"{label} is not a valid email address. You typed “{value}”.", **where))
        return out

    if ftype == "date":
        if _parse_date(value) is None:
            out.append(err(f"{label} is not a valid date.", **where))
        return out

    if ftype == "select":
        opts = fdef.get("options") or []
        if opts and str(value) not in opts:
            out.append(err(f"{label} must be one of the listed choices. You chose “{value}”.", **where))
        return out

    if ftype == "file":
        return out

    # text / textarea / phone
    text = str(value).strip()
    pattern = fdef.get("pattern")
    if pattern and not re.match(pattern, text):
        hint = fdef.get("help") or ""
        out.append(err(f"{label} is not in the expected format. {hint}".strip(), **where))
    if fdef.get("min_words") and _words(text) < fdef["min_words"]:
        out.append(err(
            f"{label} needs at least {fdef['min_words']} words. You wrote {_words(text)}.", **where))
    if fdef.get("min_items"):
        n = len(_lines(text))
        if n < fdef["min_items"]:
            out.append(err(
                f"{label} needs at least {fdef['min_items']} entries, one per line. You gave {n}.",
                **where))
    return out


# ---------------------------------------------------------------------------
# Layer 2 — named section rules
# ---------------------------------------------------------------------------

def _rows(data, section_key):
    rows = (data or {}).get(section_key) or []
    return rows if isinstance(rows, list) else []


def _vals(data, section_key):
    v = (data or {}).get(section_key) or {}
    return v if isinstance(v, dict) else {}










def _unique_emails(rows, sk, message):
    seen, out = {}, []
    for i, r in enumerate(rows):
        e = str(r.get("email", "")).strip().lower()
        if not e:
            continue
        if e in seen:
            out.append(err(f"{message}. “{e}” appears in rows {seen[e] + 1} and {i + 1}.",
                           section=sk, row=i, field="email"))
        else:
            seen[e] = i
    return out


def r_experts_unique_emails(data, ctx, sk):
    return _unique_emails(_rows(data, sk), sk, "No two experts may share an email address")



def r_programme_duration_semesters(data, ctx, sk):
    out = []
    for i, r in enumerate(_rows(data, sk)):
        yrs, sems = _int(r.get("duration_years")), _int(r.get("semesters"))
        if yrs and sems and sems != yrs * 2:
            out.append(err(f"A {yrs}-year programme has {yrs * 2} semesters, not {sems}.",
                           section=sk, row=i, field="semesters"))
        deg = r.get("degree_level") or ""
        if deg.startswith("UG - 3 Year") and yrs != 3:
            out.append(err(f"“{deg}” must have a duration of 3 years.", section=sk, row=i,
                           field="duration_years"))
        if deg.startswith("UG - 4 Year") and yrs != 4:
            out.append(err(f"“{deg}” must have a duration of 4 years.", section=sk, row=i,
                           field="duration_years"))
    return out


def r_programme_unique_codes(data, ctx, sk):
    seen, out = {}, []
    for i, r in enumerate(_rows(data, sk)):
        c = str(r.get("programme_code", "")).strip().upper()
        if not c:
            continue
        if c in seen:
            out.append(err(f"Programme code “{c}” is used twice, in rows {seen[c] + 1} and {i + 1}.",
                           section=sk, row=i, field="programme_code"))
        else:
            seen[c] = i
    return out


def r_programmes_offered_valid(data, ctx, sk):
    """Department Information → Programmes offered.

    Every row is kept or removed; a row the department added needs a code, a
    name and a degree, and no code may appear twice. At least one programme
    has to stay, because every later stage is filed per programme.
    """
    rows = _rows(data, sk)
    out, seen = [], {}
    for i, r in enumerate(rows):
        if r.get("source") == "new":
            if _is_blank(r.get("programme_name")):
                out.append(err(f"Programme {i + 1}: the new programme needs a name.",
                               section=sk, row=i, field="programme_name"))
            code = str(r.get("programme_code") or "").strip()
            if not code:
                out.append(err(f"Programme {i + 1}: the new programme needs a code.",
                               section=sk, row=i, field="programme_code"))
            elif not re.fullmatch(r"[A-Za-z0-9\-]{2,20}", code):
                out.append(err(f"Programme code “{code}” may use only letters, numbers and "
                               f"hyphens (2–20 characters).",
                               section=sk, row=i, field="programme_code"))
            if _is_blank(r.get("degree")):
                out.append(err(f"Programme {i + 1}: choose UG, PG or another degree level.",
                               section=sk, row=i, field="degree"))
        if r.get("decision") == "remove" and r.get("source") != "new":
            why = r.get("removal_reason")
            if _is_blank(why):
                out.append(err(f"Say why “{r.get('programme_code')}” is being removed.",
                               section=sk, row=i, field="removal_reason"))
            elif why == "Other" and _is_blank(r.get("removal_note")):
                out.append(err(f"“{r.get('programme_code')}” is removed for “Other” — "
                               f"add a line saying what the reason is.",
                               section=sk, row=i, field="removal_note"))
        c = str(r.get("programme_code") or "").strip().upper()
        if c:
            if c in seen:
                out.append(err(f"Programme code “{c}” is listed twice.",
                               section=sk, row=i, field="programme_code"))
            seen.setdefault(c, i)
    if not any(r.get("decision") != "remove" for r in rows):
        out.append(err("Keep or add at least one programme — every later stage is filed "
                       "per programme.", section=sk))
    return out


# ---- credit engine --------------------------------------------------------

def r_ugc_table2_minimums(data, ctx, sk):
    """Check the entered credit matrix against UGC Table 2."""
    matrix = _vals(data, sk)
    track = ctx.get("track")
    degree = ctx.get("degree_level")
    table = ctx.get("table2") or U.DEFAULT_TABLE_2
    if not track:
        return [warn("This programme is not a 3-year or 4-year UG programme, so UGC Table 2 "
                     "minimums were not applied.", section=sk)]
    out = []
    for row in table:
        spec = row.get(track) or {}
        key, label = row["key"], row["label"]
        entered = _num(matrix.get(key))
        applicable = bool(spec.get("applicable"))

        if key == "research" and degree == U.HONOURS_NO_RESEARCH:
            continue  # handled by r_ugc_research_or_lieu

        if not applicable:
            if entered:
                out.append(err(f"{label} does not apply to a {U.TRACKS[track]} programme, "
                               f"but you entered {int(entered)} credits.", section=sk, field=key))
            continue

        if entered is None:
            out.append(err(f"{label}: enter the credits your programme awards. "
                           f"The UGC minimum is {spec['min']}.", section=sk, field=key))
            continue

        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and entered < lo:
            out.append(err(f"{label}: {int(entered)} credits is below the UGC minimum of {lo} "
                           f"for a {U.TRACKS[track]} programme.", section=sk, field=key))
        if hi is not None and entered > hi:
            out.append(err(f"{label}: the UGC range is {lo} to {hi} credits. "
                           f"You entered {int(entered)}.", section=sk, field=key))
    return out


def r_ugc_total_credits(data, ctx, sk):
    matrix = _vals(data, sk)
    track = ctx.get("track")
    if not track:
        return []
    totals = ctx.get("totals") or U.DEFAULT_TOTALS
    required = totals.get(track)
    entered = sum(_num(v) or 0 for k, v in matrix.items() if k != "total")
    out = []
    if entered < required:
        out.append(err(f"Total credits come to {int(entered)}. A {U.TRACKS[track]} programme must "
                       f"award at least {required} credits — you are short by "
                       f"{int(required - entered)}.", section=sk, field="total"))
    elif entered > required * 1.15:
        out.append(warn(f"Total credits come to {int(entered)}, well above the {required} required "
                        f"for a {U.TRACKS[track]} programme. Confirm this is intended.",
                        section=sk, field="total"))
    return out


def r_ugc_research_or_lieu(data, ctx, sk):
    """Honours without research: 3 courses / 12 credits in lieu."""
    degree = ctx.get("degree_level")
    if degree != U.HONOURS_NO_RESEARCH:
        return []
    matrix = _vals(data, sk)
    lieu_credits = _num(matrix.get("in_lieu_credits"))
    lieu_courses = _int(matrix.get("in_lieu_courses"))
    rule = U.IN_LIEU_RULE
    out = []
    if lieu_credits != rule["credits"]:
        out.append(err(f"{rule['note']} Enter {rule['credits']} credits in lieu — "
                       f"you entered {'nothing' if lieu_credits is None else int(lieu_credits)}.",
                       section=sk, field="in_lieu_credits"))
    if lieu_courses != rule["courses"]:
        out.append(err(f"{rule['note']} Enter {rule['courses']} courses in lieu — "
                       f"you entered {'nothing' if lieu_courses is None else lieu_courses}.",
                       section=sk, field="in_lieu_courses"))
    return out


def r_ltpe_credit_arithmetic(data, ctx, sk):
    cfg = U.DEFAULT_OTHER_RULES
    w = cfg["credit_from_hours"]
    tol = cfg["credit_arithmetic_tolerance"]
    out = []
    for i, r in enumerate(_rows(data, sk)):
        l, t, p, e = (_num(r.get(k)) for k in ("l", "t", "p", "e"))
        cr = _num(r.get("credits"))
        if None in (l, t, p, e) or cr is None:
            continue
        expected = l * w["lecture"] + t * w["tutorial"] + p * w["practical"] + e * w["experiential"]
        if abs(expected - cr) > tol:
            out.append(err(
                f"Course {r.get('course_code') or f'in row {i + 1}'}: L-T-P-E of "
                f"{int(l)}-{int(t)}-{int(p)}-{int(e)} works out to {expected:g} credits, "
                f"but you entered {cr:g}.", section=sk, row=i, field="credits"))
        if cr > cfg["max_credits_per_course"]:
            out.append(err(f"Course {r.get('course_code') or f'in row {i + 1}'}: "
                           f"{cr:g} credits exceeds the {cfg['max_credits_per_course']}-credit "
                           f"ceiling for a single course.", section=sk, row=i, field="credits"))
    return out


def r_credit_marks_ratio(data, ctx, sk):
    per = U.DEFAULT_OTHER_RULES["marks_per_credit"]
    out = []
    for i, r in enumerate(_rows(data, sk)):
        cr, tot = _num(r.get("credits")), _num(r.get("total_marks"))
        if cr is None or tot is None:
            continue
        expected = cr * per
        if abs(expected - tot) > 0.01:
            out.append(err(
                f"Course {r.get('course_code') or f'in row {i + 1}'}: {cr:g} credits carries "
                f"{expected:g} marks at 1 credit = {per} marks, but total marks is {tot:g}.",
                section=sk, row=i, field="total_marks"))
    return out


def r_marks_add_up(data, ctx, sk):
    out = []
    for i, r in enumerate(_rows(data, sk)):
        cia, ese, tot = (_num(r.get(k)) for k in ("cia", "ese", "total_marks"))
        if None in (cia, ese, tot):
            continue
        if abs((cia + ese) - tot) > 0.01:
            out.append(err(
                f"Course {r.get('course_code') or f'in row {i + 1}'}: CIA {cia:g} + ESE {ese:g} "
                f"= {cia + ese:g}, which does not match the total of {tot:g}.",
                section=sk, row=i, field="total_marks"))
    return out


def r_semester_within_duration(data, ctx, sk):
    sems = ctx.get("semesters")
    if not sems:
        return []
    out = []
    for i, r in enumerate(_rows(data, sk)):
        s = _int(r.get("semester"))
        if s and s > sems:
            out.append(err(f"Semester {s} is outside this programme, which has {sems} semesters.",
                           section=sk, row=i, field="semester"))
    return out


def r_unique_course_codes(data, ctx, sk):
    seen, out = {}, []
    for i, r in enumerate(_rows(data, sk)):
        c = str(r.get("course_code", "")).strip().upper()
        if not c:
            continue
        if c in seen:
            out.append(err(f"Course code “{c}” is used twice, in rows {seen[c] + 1} and {i + 1}.",
                           section=sk, row=i, field="course_code"))
        else:
            seen[c] = i
    return out


def r_category_totals_match_summary(data, ctx, sk):
    """Credits in the course grid must add up to the credit matrix in Section B."""
    matrix = _vals(data, "credit_summary")
    if not matrix:
        return []
    tally = {}
    for r in _rows(data, sk):
        key = U.NEP_CATEGORY_TO_KEY.get(r.get("nep_category"))
        cr = _num(r.get("credits"))
        if key and cr is not None:
            tally[key] = tally.get(key, 0) + cr
    out = []
    for key, declared in matrix.items():
        if key.startswith("in_lieu") or key == "total":
            continue
        d = _num(declared)
        if d is None:
            continue
        got = tally.get(key, 0)
        if abs(got - d) > 0.01:
            label = next((r["label"] for r in U.DEFAULT_TABLE_2 if r["key"] == key), key)
            out.append(err(
                f"{label}: Section B declares {d:g} credits but the courses you listed in "
                f"Section C add up to {got:g}.", section=sk, field=key))
    return out


def r_course_codes_known(data, ctx, sk):
    known = ctx.get("known_course_codes") or set()
    if not known:
        return []
    out = []
    for i, r in enumerate(_rows(data, sk)):
        c = str(r.get("course_code", "")).strip().upper()
        if c and c not in known:
            out.append(err(f"Course code “{c}” does not appear in the programme structure you "
                           f"submitted in the Curriculum & Regulations stage.",
                           section=sk, row=i, field="course_code"))
    return out


def r_bloom_verbs_present(data, ctx, sk):
    out = []
    for i, r in enumerate(_rows(data, sk)):
        for j, line in enumerate(_lines(r.get("outcomes"))):
            first = re.sub(r"^(CO\s*\d+\s*[:.\-]?\s*)", "", line, flags=re.I).strip().split(" ")[0]
            if first.lower().strip(".,:") not in BLOOM_VERBS:
                out.append(warn(
                    f"Course {r.get('course_code') or f'row {i + 1}'}, outcome {j + 1} starts with "
                    f"“{first}”, which is not a Bloom's taxonomy action verb.",
                    section=sk, row=i, field="outcomes"))
    return out


def r_co_po_wellformed(data, ctx, sk):
    pat = re.compile(r"^(CO\d+\s*-\s*(PO|PSO)\d+\s*\([123]\)\s*,?\s*)+$", re.I)
    out = []
    for i, r in enumerate(_rows(data, sk)):
        v = str(r.get("co_po_map", "")).strip()
        if v and not pat.match(v):
            out.append(err(
                f"Course {r.get('course_code') or f'row {i + 1}'}: CO-PO mapping must look like "
                f"“CO1-PO1(3), CO2-PSO1(2)”. Strength must be 1, 2 or 3.",
                section=sk, row=i, field="co_po_map"))
    return out


def r_revision_change_needs_justification(data, ctx, sk):
    out = []
    for i, r in enumerate(_rows(data, sk)):
        changed = (str(r.get("existing_title", "")).strip() != str(r.get("revised_title", "")).strip()
                   or _num(r.get("existing_credits")) != _num(r.get("revised_credits")))
        if changed and _words(r.get("justification")) < 10:
            out.append(err(f"Row {i + 1}: this course changed, so the justification must be at "
                           f"least 10 words.", section=sk, row=i, field="justification"))
    return out


def r_revision_percent_threshold(data, ctx, sk):
    thr = U.DEFAULT_OTHER_RULES["revision_benchmark_threshold"]
    out = []
    for i, r in enumerate(_rows(data, sk)):
        p = _num(r.get("percent_changed"))
        if p is not None and p >= thr and _is_blank(r.get("benchmark")):
            out.append(err(f"Row {i + 1}: a revision of {p:g}% needs benchmarking evidence "
                           f"(anything at or above {thr}%).", section=sk, row=i, field="benchmark"))
    return out


def r_all_stakeholder_groups_present(data, ctx, sk):
    need = {"Faculty", "Student", "Alumni", "Employer", "Industry", "Academic Peer"}
    have = {r.get("source") for r in _rows(data, sk)}
    missing = sorted(need - have)
    if missing:
        return [err("Feedback is missing from these stakeholder groups: " + ", ".join(missing),
                    section=sk)]
    return []


def r_feedback_date_within_year(data, ctx, sk):
    out = []
    today = date.today()
    for i, r in enumerate(_rows(data, sk)):
        d = _parse_date(r.get("collected_on"))
        if d and d > today:
            out.append(err(f"Row {i + 1}: feedback cannot be collected on a future date.",
                           section=sk, row=i, field="collected_on"))
        elif d and (today - d).days > 730:
            out.append(warn(f"Row {i + 1}: this feedback is more than two years old.",
                            section=sk, row=i, field="collected_on"))
    return out


def r_notice_seven_days(data, ctx, sk):
    v = _vals(data, sk)
    days = U.DEFAULT_OTHER_RULES["meeting_notice_days"]
    nd, md = _parse_date(v.get("notice_date")), _parse_date(v.get("meeting_date"))
    if nd and md:
        gap = (md - nd).days
        if gap < days:
            return [err(f"The notice must be circulated at least {days} days before the meeting. "
                        f"Yours went out {gap} day(s) before.", section=sk, field="notice_date")]
    return []


def r_quorum_met(data, ctx, sk):
    v = _vals(data, sk)
    present, absent = _int(v.get("members_present")), _int(v.get("members_absent"))
    if present is None or absent is None:
        return []
    total = present + absent
    if total and present / total < U.DEFAULT_OTHER_RULES["quorum_fraction"]:
        return [err(f"Quorum was not met: {present} of {total} members attended. "
                    f"More than half must be present.", section=sk, field="members_present")]
    return []


def r_approval_chain_order(data, ctx, sk):
    rows = _rows(data, sk)
    out, prev_d, prev_l = [], None, None
    for i, r in enumerate(rows):
        d = _parse_date(r.get("approved_on"))
        if d and prev_d and d < prev_d:
            out.append(err(f"“{r.get('level')}” is dated {d}, before “{prev_l}” on {prev_d}. "
                           f"Approvals must run in order.", section=sk, row=i, field="approved_on"))
        if d:
            prev_d, prev_l = d, r.get("level")
    return out


def r_approval_after_meeting(data, ctx, sk):
    md = _parse_date(((ctx.get("prior") or {}).get("meeting_docs") or {})
                     .get("meeting", {}).get("meeting_date"))
    if not md:
        return []
    out = []
    for i, r in enumerate(_rows(data, sk)):
        d = _parse_date(r.get("approved_on"))
        if d and d < md:
            out.append(err(f"“{r.get('level')}” is dated {d}, before the Board of Studies meeting "
                           f"on {md}.", section=sk, row=i, field="approved_on"))
    return out


def r_plan_applicable_needs_detail(data, ctx, sk):
    out = []
    for i, r in enumerate(_rows(data, sk)):
        if r.get("applicable") == "Yes":
            if _is_blank(r.get("owner")):
                out.append(err(f"“{r.get('item')}” is marked applicable, so it needs an owner.",
                               section=sk, row=i, field="owner"))
            if _is_blank(r.get("target_date")):
                out.append(err(f"“{r.get('item')}” is marked applicable, so it needs a target date.",
                               section=sk, row=i, field="target_date"))
    return out


RULES = {name[2:]: fn for name, fn in list(globals().items())
         if name.startswith("r_") and callable(fn)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def validate_stage(stage_key: str, data: dict, ctx: dict | None = None):
    """Validate one stage payload. Returns (issues, summary)."""
    ctx = ctx or {}
    stage = STAGE_BY_KEY.get(stage_key)
    if not stage:
        return [err(f"Unknown stage “{stage_key}”.")], {"errors": 1, "warnings": 0}

    issues = []
    data = data or {}

    for section in stage.get("sections", []):
        sk = section["key"]
        stype = section.get("type", "fields")

        if stype == "table":
            rows = _rows(data, sk)
            min_rows = section.get("min_rows", 0)
            if len(rows) < min_rows:
                issues.append(err(
                    f"{section['title']} needs at least {min_rows} row(s). You have {len(rows)}.",
                    section=sk))
            for i, row in enumerate(rows):
                for col in section.get("columns", []):
                    issues += validate_field(col, row.get(col["name"]), sk, i)

        elif stype == "credit_matrix":
            pass  # handled entirely by the named UGC rules below

        elif stype == "programme_list":
            pass  # rows are checked by the section's rule

        else:
            vals = _vals(data, sk)
            for f in section.get("fields", []):
                issues += validate_field(f, vals.get(f["name"]), sk, None)

        for rule_name in section.get("rules", []) or []:
            fn = RULES.get(rule_name)
            if fn:
                try:
                    issues += fn(data, ctx, sk) or []
                except Exception as exc:  # a rule must never take the page down
                    issues.append(warn(f"Rule “{rule_name}” could not be evaluated: {exc}",
                                       section=sk))

    summary = {
        "errors": sum(1 for i in issues if i["level"] == "error"),
        "warnings": sum(1 for i in issues if i["level"] == "warning"),
    }
    return issues, summary


def build_context(submission: dict, programme: dict | None = None, rules_doc: dict | None = None):
    """Assemble the context a stage validation needs from the stored submission."""
    ctx = {
        "prior": {k: v.get("data", {}) for k, v in (submission.get("stages") or {}).items()},
        "table2": (rules_doc or {}).get("table2") or U.DEFAULT_TABLE_2,
        "totals": (rules_doc or {}).get("totals") or U.DEFAULT_TOTALS,
    }
    if programme:
        deg = programme.get("degree_level")
        ctx["degree_level"] = deg
        ctx["track"] = U.get_track(deg)
        ctx["semesters"] = _int(programme.get("semesters"))
        ctx["programme_code"] = programme.get("programme_code")

        curric = ((submission.get("programmes") or {})
                  .get(programme.get("programme_code"), {})
                  .get("ugc_curriculum", {}).get("data", {}))
        ctx["known_course_codes"] = {
            str(r.get("course_code", "")).strip().upper()
            for r in (curric.get("semester_structure") or [])
            if r.get("course_code")
        }
    return ctx
