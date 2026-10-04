"""A short summary of an uploaded PDF — by an AI service when one is set up,
else (or when it fails) by the built-in reader in local_summary.py.

The text layer is read first. BoS documents are often signed scans with no
text in them, so when there is none the first pages are drawn as pictures
and sent instead. A summary is made once per file and kept on its record in
`files`; asking again returns the kept one unless a fresh one is asked for.

Needs AI_API_KEY in the server's .env. Without it the portal works as
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


def ai_enabled() -> bool:
    return bool(current_app.config.get("AI_API_KEY"))


def field_label(stage_key: str, field: str) -> str:
    stage = STAGE_BY_KEY.get(stage_key) or {}
    for sec in stage.get("sections", []):
        for f in sec.get("fields", []):
            if f.get("name") == field:
                return f.get("label") or field
    return field.replace("_", " ").capitalize()


def _pdf_text(path: Path) -> tuple[str, int]:
    from .pdflock import PDF_LOCK
    with PDF_LOCK:
        return _pdf_text_unlocked(path)


def _pdf_text_unlocked(path: Path) -> tuple[str, int]:
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
    from .pdflock import PDF_LOCK
    with PDF_LOCK:
        return _pdf_images_unlocked(path)


def _pdf_images_unlocked(path: Path) -> list[str]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        urls = []
        for i in range(min(len(doc), MAX_PAGES_AS_IMAGES)):
            img = doc[i].render(scale=1.3).to_pil().convert("RGB")
            img.thumbnail((1200, 1200))
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


def _reason(detail: str) -> str:
    """The service's own words from an error body. Services put them in
    different places: xAI in "error", OpenAI/Gemini in "error.message",
    Mistral in "message". None of them ever echo the key."""
    try:
        body = json.loads(detail)
    except ValueError:
        return detail.strip()[:220]
    if isinstance(body, list) and body:
        body = body[0]
    if not isinstance(body, dict):
        return str(body)[:220]
    r = body.get("error") or body.get("message") or body.get("detail") or detail
    if isinstance(r, dict):
        r = r.get("message") or str(r)
    return str(r).strip()[:220]


RETRIES = 3   # on 429 / 5xx; free tiers often allow one request a second


def _call(messages: list, model: str) -> str:
    import time
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": 0.2, "max_tokens": 2000}).encode()
    name = current_app.config.get("AI_NAME") or "The AI service"
    for attempt in range(RETRIES):
        req = urllib.request.Request(current_app.config["AI_API_URL"], data=body, method="POST", headers={
            "Authorization": f"Bearer {current_app.config['AI_API_KEY']}",
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            reason = _reason(detail)
            current_app.logger.warning("AI %s for model %s (try %d): %s", e.code, model, attempt + 1, reason)
            if (e.code == 429 or e.code >= 500) and attempt < RETRIES - 1:
                # wait as told, or 2 s then 5 s
                try:
                    wait = float(e.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    wait = 0
                time.sleep(min(max(wait, (2, 5)[attempt]), 10))
                continue
            if e.code == 401:
                raise SummaryError(f"{name} refused the API key (401) — check AI_API_KEY in .env. "
                                   f"{name} says: {reason}")
            if e.code == 403:
                raise SummaryError(f"{name} refused the request (403). {name} says: {reason}")
            if e.code in (400, 404) and "model" in reason.lower():
                raise SummaryError(f"{name} does not know the model “{model}” — set AI_MODEL in .env. "
                                   f"{name} says: {reason}")
            if e.code == 429:
                raise SummaryError(f"{name} says there are too many requests (429), even after "
                                   f"waiting and trying again. {name} says: {reason}")
            raise SummaryError(f"{name} could not summarise this file ({e.code}). {name} says: {reason}")
        except (urllib.error.URLError, TimeoutError) as e:
            current_app.logger.warning("AI service unreachable: %s", e)
            raise SummaryError(f"Could not reach {name} from the server — try again shortly.")
    try:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):          # some services answer in parts
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        return content.strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise SummaryError(f"{name} sent back an empty answer.")


def summarise(rec: dict, path: Path, refresh: bool = False) -> dict:
    """The summary for this file record, made now if there is none kept."""
    from . import local_summary as local
    if rec.get("summary") and not refresh:
        return {"summary": rec["summary"], "at": rec.get("summary_at"), "cached": True,
                "by": rec.get("summary_by") or current_app.config["AI_NAME"]}
    if Path(rec["original_name"]).suffix.lower() != ".pdf":
        raise SummaryError("Only PDF files can be summarised.")
    if not path.exists():
        raise SummaryError("The file is no longer on the server.")

    label = field_label(rec.get("stage", ""), rec.get("field", ""))
    try:
        text, pages = _pdf_text(path)
    except Exception:
        raise SummaryError("This PDF could not be opened — it may be damaged or password-protected.")
    has_text = len(text) >= MIN_TEXT

    summary, by, model, ai_problem = None, None, None, None
    if ai_enabled():
        prompt = PROMPT.format(label=label, name=rec["original_name"])
        try:
            if has_text:
                content = f"{prompt}\n\nThe document ({pages} pages):\n\n{text}"
                model = current_app.config["AI_MODEL"]
            else:
                # a scan: send the first pages as pictures
                try:
                    images = _pdf_images(path)
                except Exception:
                    raise SummaryError("The pages of this PDF could not be drawn to be read.")
                content = [{"type": "text", "text": prompt + f"\n\nThe document has {pages} pages; "
                            f"the first {len(images)} are attached as images."}]
                content += [{"type": "image_url", "image_url": {"url": u}} for u in images]
                model = current_app.config["AI_VISION_MODEL"]
            summary = _call([{"role": "user", "content": content}], model)
            by = current_app.config["AI_NAME"]
        except SummaryError as e:
            ai_problem = str(e)

    if summary is None:
        # the built-in reader: always there, never leaves the server
        summary = (local.summarise_text(text, pages, label, rec["original_name"])
                   if has_text else local.scan_note(pages))
        by, model = local.NAME, "local"
        if ai_problem:
            summary += f"\n(AI not used this time: {ai_problem})"

    at = now()
    # a built-in summary written because the AI failed is not kept, so the
    # next press tries the AI again
    keep = not ai_problem
    if keep:
        get_db().files.update_one({"_id": rec["_id"]},
                                  {"$set": {"summary": summary, "summary_at": at,
                                            "summary_model": model, "summary_by": by}})
    return {"summary": summary, "at": at, "cached": False, "by": by}
