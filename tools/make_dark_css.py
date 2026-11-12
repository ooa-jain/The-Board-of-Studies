"""
Build app/static/css/dark.css — the portal's dark theme — from its light
stylesheets, so the two can never drift apart.

    pip install tinycss2        # only needed to run this, not to run the portal
    python tools/make_dark_css.py

Every rule in app.css, erp.css, shell.css, admin.css and login.css that sets
a colour (text, background, border, outline, shadow, icon fill) is repeated
under html[data-theme="dark"], with each colour turned into its dark-theme
counterpart by the part it plays:

    background   white and pale tints  -> deep navy-greys (tints keep a hint)
                 navy fills (buttons)  -> a brighter blue that reads on dark
    text         dark ink              -> light ink; navy -> pale blue
                 status colours        -> lifted so they read on dark
    lines        pale greys            -> dark lines

A colour given as var(--x) is looked up and turned the same way, so a
variable used both as a fill and as text gets the right colour in each place.
Every colour declaration is repeated (changed or not), so the dark rules keep
the light rules' order and specificity exactly. Hand-made touches for the
dark theme live in theme.css, not here.
"""

from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

import tinycss2

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "app" / "static" / "css"
SOURCES = ["app.css", "erp.css", "shell.css", "admin.css", "login.css"]
OUT = CSS / "dark.css"
DARK = 'html[data-theme="dark"]'
# classes the portal puts on <html> itself, so the dark rule attaches to it
ON_HTML = ("side-collapsed", "is-preloading")
# what each property's colours are for
ROLE = {"color": "text", "-webkit-text-fill-color": "text", "caret-color": "text",
        "text-decoration": "text", "text-decoration-color": "text", "fill": "text", "stroke": "text",
        "accent-color": "text",
        "background": "bg", "background-color": "bg", "background-image": "bg",
        "border": "line", "border-top": "line", "border-right": "line", "border-bottom": "line",
        "border-left": "line", "border-color": "line", "border-top-color": "line",
        "border-right-color": "line", "border-bottom-color": "line", "border-left-color": "line",
        "border-block": "line", "border-inline": "line", "border-block-start": "line",
        "border-block-end": "line", "border-inline-start": "line", "border-inline-end": "line",
        "outline": "line", "outline-color": "line", "column-rule": "line",
        "box-shadow": "shadow", "text-shadow": "shadow"}
NAMED = {"white": (255, 255, 255, 1.0), "black": (0, 0, 0, 1.0)}


# ----------------------------------------------------------------- colours
def parse_hex(h):
    h = h.lower()
    if not re.fullmatch(r"[0-9a-f]{3,8}", h) or len(h) not in (3, 4, 6, 8):
        return None
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, a


def parse_func(tok):
    """rgb()/rgba()/hsl()/hsla() -> (r, g, b, a), or None."""
    nums = [t for t in tok.arguments if t.type in ("number", "percentage", "dimension")]
    if len(nums) < 3:
        return None
    vals = [t.value for t in nums]
    if tok.lower_name in ("rgb", "rgba"):
        r, g, b = (v * 2.55 if t.type == "percentage" else v for v, t in zip(vals[:3], nums[:3]))
    else:
        h, s, l = vals[0] / 360, vals[1] / 100, vals[2] / 100
        r, g, b = (x * 255 for x in colorsys.hls_to_rgb(h, l, s))
    a = 1.0
    if len(nums) > 3:
        a = nums[3].value / 100 if nums[3].type == "percentage" else nums[3].value
    return r, g, b, a


def fmt(r, g, b, a):
    r, g, b = (max(0, min(255, round(x))) for x in (r, g, b))
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {round(a, 3)})"


def turn(rgba, role):
    """A light-theme colour -> its dark-theme counterpart, by role."""
    r, g, b, a = rgba
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hue = h * 360
    blue = 190 <= hue <= 265

    if role == "shadow":
        if l < 0.8:
            return rgba                          # a shadow is a shadow
        role = "bg"                              # a white ring: the surface
    # greys take the portal's navy tint, so the dark reads as navy-black
    if s < 0.3 and role in ("bg", "line", "text"):
        h, s = 220 / 360, max(s, 0.16 if role != "text" else 0.14)
    if role == "bg":
        if l >= 0.8:
            l, s = 0.085 + (1 - l) * 0.75, min(s, 0.5)
        elif l <= 0.32:
            if s >= 0.25:
                l, s = 0.42, min(s, 0.72)        # navy fills -> a blue that reads
            else:
                l = max(l, 0.19)
    elif role == "text":
        if l <= 0.5:
            if s >= 0.35 and blue:
                l, s = 0.8, min(s, 0.75)         # navy ink -> pale blue
            elif s >= 0.35:
                l = 0.7                          # red / green ink, lifted
            else:
                l = 0.93 - l * 0.55              # grey ink -> light ink
        elif l < 0.78:
            l = max(l, 0.68 if s < 0.15 else 0.66)
    elif role == "line":
        if l >= 0.75:
            l, s = 0.17 + (1 - l) * 0.55, min(s, 0.3)
        elif l <= 0.35:
            l = 0.55 if s >= 0.25 else 0.42
    r2, g2, b2 = (x * 255 for x in colorsys.hls_to_rgb(h, l, s))
    return r2, g2, b2, a


# ---------------------------------------------------------- the variables
def collect_vars(sheets):
    out = {}
    for rules in sheets:
        for rule in walk(rules):
            for d in decls(rule):
                if d.name.startswith("--") and d.name not in out:
                    out[d.name] = d.value
    return out


def resolve_var(name, table, seen=()):
    """--x -> the colour it holds (r, g, b, a), or None."""
    if name in seen or name not in table:
        return None
    toks = [t for t in table[name] if t.type not in ("whitespace", "comment")]
    if len(toks) != 1:
        return None
    return color_of(toks[0], table, seen + (name,))


def color_of(tok, table, seen=()):
    if tok.type == "hash":
        return parse_hex(tok.value)
    if tok.type == "ident" and tok.lower_value in NAMED:
        return NAMED[tok.lower_value]
    if tok.type == "function" and tok.lower_name in ("rgb", "rgba", "hsl", "hsla"):
        return parse_func(tok)
    if tok.type == "function" and tok.lower_name == "var":
        args = [t for t in tok.arguments if t.type not in ("whitespace", "comment")]
        if args and args[0].type == "ident":
            c = resolve_var(args[0].value, table, seen)
            if c is None and len(args) > 2 and args[1].type == "literal" and args[1].value == ",":
                c = color_of(args[2], table, seen)
            return c
    return None


def has_color(tokens, table, seen=()):
    for t in tokens:
        if color_of(t, table) is not None:
            return True
        if t.type == "function":
            if t.lower_name == "var":
                args = [a for a in t.arguments if a.type == "ident"]
                if args and args[0].value in table and args[0].value not in seen:
                    if has_color(table[args[0].value], table, seen + (args[0].value,)):
                        return True
            elif has_color(t.arguments, table, seen):
                return True
    return False


def transform(tokens, role, table, seen=()):
    out = []
    for tok in tokens:
        c = color_of(tok, table)
        if c is None and tok.type == "function" and tok.lower_name == "var":
            # a variable holding a gradient or a shadow: written out, turned
            args = [a for a in tok.arguments if a.type == "ident"]
            name = args[0].value if args else None
            if name in table and name not in seen and has_color(table[name], table):
                out.extend(transform(table[name], role, table, seen + (name,)))
                continue
        if c is not None:
            out.append(tinycss2.ast.LiteralToken(tok.source_line, tok.source_column, fmt(*turn(c, role))))
        elif tok.type == "function":
            tok = tinycss2.ast.FunctionBlock(tok.source_line, tok.source_column, tok.name,
                                             transform(tok.arguments, role, table, seen))
            out.append(tok)
        else:
            out.append(tok)
    return out


# ------------------------------------------------------------- the rules
def walk(rules):
    for r in rules:
        if r.type == "qualified-rule":
            yield r
        elif r.type == "at-rule" and r.lower_at_keyword in ("media", "supports") and r.content:
            yield from walk(tinycss2.parse_rule_list(r.content, skip_comments=True, skip_whitespace=True))


def decls(rule):
    return [d for d in tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True)
            if d.type == "declaration"]


def split_selectors(text):
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def prefix(sel):
    if sel.startswith("::view-transition"):
        return None
    if sel.startswith(":root"):
        return DARK + sel[5:]
    if re.match(r"html(?![\w-])", sel):
        return DARK + sel[4:]
    for cls in ON_HTML:
        if re.match(r"\." + cls + r"(?![\w-])", sel):
            return DARK + sel
    return DARK + " " + sel


def dark_rule(rule, table):
    body = []
    for d in decls(rule):
        role = ROLE.get(d.lower_name)
        if not role:
            continue
        value = tinycss2.serialize(transform(d.value, role, table)).strip()
        body.append(f"  {d.name}: {value}{' !important' if d.important else ''};")
    if not body:
        return None
    sels = [s for s in (prefix(s) for s in split_selectors(tinycss2.serialize(rule.prelude).strip())) if s]
    if not sels:
        return None
    return ",\n".join(sels) + " {\n" + "\n".join(body) + "\n}"


def render(rules, table, indent=""):
    out = []
    for r in rules:
        if r.type == "qualified-rule":
            x = dark_rule(r, table)
            if x:
                out.append(x)
        elif r.type == "at-rule" and r.lower_at_keyword in ("media", "supports") and r.content:
            prelude = tinycss2.serialize(r.prelude).strip()
            if r.lower_at_keyword == "media" and re.fullmatch(r"print", prelude):
                continue                          # paper stays light
            inner = render(tinycss2.parse_rule_list(r.content, skip_comments=True, skip_whitespace=True), table)
            if inner:
                out.append(f"@{r.at_keyword} {prelude} {{\n" + "\n".join(inner) + "\n}")
    return out


def main():
    sheets = []
    for name in SOURCES:
        sheets.append(tinycss2.parse_stylesheet((CSS / name).read_text(encoding="utf-8"),
                                                skip_comments=True, skip_whitespace=True))
    table = collect_vars(sheets)
    parts = [f"/* Generated by tools/make_dark_css.py from {', '.join(SOURCES)} — do not edit;\n"
             f"   change the light stylesheets (or theme.css) and run it again. */",
             f"{DARK} {{ color-scheme: dark; }}"]
    for name, rules in zip(SOURCES, sheets):
        parts.append(f"\n/* ---- {name} ---- */")
        parts.extend(render(rules, table))
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
