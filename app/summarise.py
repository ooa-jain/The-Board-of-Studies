"""A short summary of an uploaded PDF, written by Grok (xAI).

The text layer is read first. BoS documents are often signed scans with no
text in them, so when there is none the first pages are drawn as pictures
and sent instead. A summary is made once per file and kept on its record in
`files`; asking again returns the kept one unless a fresh one is asked for.

Needs XAI_API_KEY in the server's .env. Without it the portal works as
before and the Summary button says the feature is not set up.
"""

from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path

from flask import current_app

from .db import get_db, now
from .schema import STAGE_BY_KEY

MAX_CHARS = 24000          # of text sent; a BoS document rarely needs more
MAX_PAGES_AS_IMAGES = 4    # for a scan
MIN_TEXT = 200             # below this the PDF is treated as a scan


class SummaryError(Exception):
    """Said to the person as it is."""


def enabled() -> bool:
    return bool(current_app.config.get("XAI_API_KEY"))


def field_label(stage_key: str, field: str) -> str:
    stage = STAGE_BY_KEY.get(stage_key) or {}
    for sec in stage.get("sections", []):
        for f in sec.get("fields", []):
            if f.get("name") == field:
                return f.get("label") or field
    return field.replace("_", " ").capitalize()


def _pdf_text(path: Path) -> tuple[str, int]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        out, total = [], 0
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            t = tp.get_text_range().strip()
            tp.close()
            page.close()
            if t:
                out.append(f"--- page {i + 1} ---\n{t}")
                total += len(t)
            if total > MAX_CHARS:
                break
        return "\n".join(out)[:MAX_CHARS], len(doc)
    finally:
        doc.close()


def _pdf_images(path: Path) -> list[str]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        urls = []
        for i in range(min(len(doc), MAX_PAGES_AS_IMAGES)):
            img = doc[i].render(scale=1.3).to_pil().convert("RGB")
            img.thumbnail((1400, 1400))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)
            urls.append("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode())
        return urls
    finally:
        doc.close()


PROMPT = (
    "You are helping the Office of Academics at JAIN (Deemed-to-be University) check "
    "documents a department uploaded for its Board of Studies (BoS) record.\n"
    "The department uploaded this file as: “{label}”. File name: {name}.\n\n"
    "Write a short summary for a busy reviewer, in plain English:\n"
    "- First line: what the document is, in one sentence.\n"
    "- Then 3 to 5 bullets with the key facts (dates, meeting, names and roles, "
    "programmes, decisions, counts) — only what the document actually says.\n"
    "- Last line starting 'Check:' — say whether it looks like the right document for "
    "“{label}”, and anything missing or unclear (unsigned, undated, wrong year, "
    "unreadable pages). Write 'Check: looks right.' if nothing stands out.\n"
    "Keep it under 120 words. No preamble, no markdown headings."
)


def _call(messages: list, model: str) -> str:
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": 0.2, "max_tokens": 450}).encode()
    req = urllib.request.Request(current_app.config["XAI_API_URL"], data=body, method="POST", headers={
        "Authorization": f"Bearer {current_app.config['XAI_API_KEY']}",
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        current_app.logger.warning("xAI %s for model %s: %s", e.code, model, detail)
        # xAI says why in its body: a bad key, no credits, a model the key
        # may not use. Pass its words on — they never contain the key.
        try:
            reason = json.loads(detail).get("error") or detail
            if isinstance(reason, dict):
                reason = reason.get("message") or str(reason)
        except ValueError:
            reason = detail
        reason = str(reason).strip()[:220]
        if e.code == 401:
            raise SummaryError(f"Grok refused the API key (401). xAI says: {reason}")
        if e.code == 403:
            raise SummaryError(f"Grok refused the request (403). xAI says: {reason}")
        if e.code in (400, 404) and "model" in reason.lower():
            raise SummaryError(f"Grok does not know the model “{model}” — set XAI_MODEL in .env. "
                               f"xAI says: {reason}")
        if e.code == 429:
            raise SummaryError("Grok is busy or the key's limit is reached — try again in a minute.")
        raise SummaryError(f"Grok could not summarise this file ({e.code}).")
    except (urllib.error.URLError, TimeoutError) as e:
        current_app.logger.warning("xAI unreachable: %s", e)
        raise SummaryError("Could not reach Grok from the server — try again shortly.")
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise SummaryError("Grok sent back an empty answer.")


def summarise(rec: dict, path: Path, refresh: bool = False) -> dict:
    """The summary for this file record, made now if there is none kept."""
    if rec.get("summary") and not refresh:
        return {"summary": rec["summary"], "at": rec.get("summary_at"), "cached": True}
    if not enabled():
        raise SummaryError("PDF summaries are not set up — add XAI_API_KEY to the server's .env.")
    if Path(rec["original_name"]).suffix.lower() != ".pdf":
        raise SummaryError("Only PDF files can be summarised.")
    if not path.exists():
        raise SummaryError("The file is no longer on the server.")

    label = field_label(rec.get("stage", ""), rec.get("field", ""))
    prompt = PROMPT.format(label=label, name=rec["original_name"])
    try:
        text, pages = _pdf_text(path)
    except Exception:
        raise SummaryError("This PDF could not be opened — it may be damaged or password-protected.")

    if len(text) >= MIN_TEXT:
        content = f"{prompt}\n\nThe document ({pages} pages):\n\n{text}"
        model = current_app.config["XAI_MODEL"]
    else:
        # a scan: send the first pages as pictures
        try:
            images = _pdf_images(path)
        except Exception:
            raise SummaryError("The pages of this PDF could not be drawn to be read.")
        content = [{"type": "text", "text": prompt + f"\n\nThe document has {pages} pages; "
                    f"the first {len(images)} are attached as images."}]
        content += [{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in images]
        model = current_app.config["XAI_VISION_MODEL"]

    summary = _call([{"role": "user", "content": content}], model)
    at = now()
    get_db().files.update_one({"_id": rec["_id"]},
                              {"$set": {"summary": summary, "summary_at": at, "summary_model": model}})
    return {"summary": summary, "at": at, "cached": False}
