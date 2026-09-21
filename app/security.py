"""
Cross-site request forgery protection.

Every state-changing request — a form post from the admin console, a JSON call
from the stage form — has to carry a token that only this browser session
knows. The session cookie is already ``SameSite=Lax``, which stops most of
this, but "most" is not a guarantee: a top-level form post from another site
still sends the cookie, and the admin console generates passwords, disables
departments and rewrites the credit rules.

Forms get the token from :func:`csrf_token` through the ``csrf_input`` macro
in ``base.html``; scripts read it from the ``csrf-token`` meta tag and send it
as ``X-CSRF-Token``.
"""

from __future__ import annotations

import hmac
import secrets

from flask import abort, jsonify, request, session

FIELD = "_csrf"
HEADER = "X-CSRF-Token"
SESSION_KEY = "_csrf_token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_token() -> str:
    """This session's token, minted on first use and stable thereafter."""
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def _submitted() -> str:
    return (request.form.get(FIELD)
            or request.headers.get(HEADER)
            or request.args.get(FIELD)
            or "")


def validate_request() -> bool:
    expected = session.get(SESSION_KEY)
    submitted = _submitted()
    if not expected or not submitted:
        return False
    return hmac.compare_digest(expected, submitted)


def protect(app):
    """Refuse unsafe requests that do not carry the session's token."""

    @app.before_request
    def _check_csrf():
        if request.method in SAFE_METHODS:
            return None
        if not app.config.get("CSRF_PROTECT", True) or app.config.get("TESTING"):
            return None
        if getattr(app.view_functions.get(request.endpoint or ""), "_csrf_exempt", False):
            return None
        if validate_request():
            return None

        app.logger.warning("CSRF token missing or stale on %s", request.path)
        wants_json = (request.is_json
                      or "application/json" in (request.headers.get("Accept") or ""))
        if wants_json:
            return jsonify({"ok": False,
                            "error": "Your session has expired. Reload the page and try again.",
                            "csrf": True}), 400
        abort(400, "Your session has expired. Go back, reload the page and try again.")

    @app.context_processor
    def _inject_token():
        return {"csrf_token": csrf_token}


def exempt(view):
    """Mark a view as not needing a token — used for nothing yet, by design."""
    view._csrf_exempt = True
    return view
