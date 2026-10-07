"""Application factory for the JAIN Office of Academics Data Portal."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, g, render_template, session

from config import Config

from . import db as database


def create_app(config_object=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object)
    # nginx passes the scheme and host on; links written into downloads
    # (Excel, Word) must be the site's https address, not 127.0.0.1
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    logging.basicConfig(
        level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
    )

    app.config["UPLOAD_ROOT"].mkdir(parents=True, exist_ok=True)

    database.init_db(app)

    from .auth import bp as auth_bp
    from .admin import bp as admin_bp
    from .dept import bp as dept_bp
    from .public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(dept_bp, url_prefix="/department")
    from .share import bp as share_bp
    app.register_blueprint(share_bp, url_prefix="/share")

    # Static files are cached for 30 days (deploy/nginx.conf). Stamp every
    # static URL with the file's mtime so a deploy changes the URL and
    # browsers fetch the new CSS/JS instead of pairing new HTML with old CSS.
    @app.url_defaults
    def _bust_static_cache(endpoint, values):
        if endpoint != "static" or "v" in values:
            return
        filename = values.get("filename")
        if not filename:
            return
        try:
            values["v"] = int((Path(app.static_folder) / filename).stat().st_mtime)
        except OSError:
            pass

    @app.before_request
    def _load_user():
        g.user = session.get("user")

    @app.context_processor
    def _inject():
        from .schema import GROUP_ORDER, STAGE_BY_KEY, STAGES
        user = session.get("user") or {}
        unread, batch_info = 0, None
        if user.get("role") == "admin":
            try:
                unread = database.get_db().notifications.count_documents({"read": False})
                from .workflow import batches
                batch_info = batches()
            except Exception:
                unread = 0
        dept_nav = None
        if user.get("role") == "department" and user.get("dept_code"):
            # the department's menu: its stages, each with where it stands
            try:
                from .workflow import get_or_create_submission, stage_board
                sub = get_or_create_submission(user["dept_code"], database.settings().get("academic_year")
                                               or app.config["ACADEMIC_YEAR"])
                dept_nav = [{"key": s["key"], "title": s["title"], "status": s["status"]}
                            for s in stage_board(sub)]
            except Exception:
                dept_nav = None
        return {
            "dept_nav": dept_nav,
            "updates_unread": unread,
            "batch_info": batch_info,
            "current_user": session.get("user"),
            "app_settings": database.settings(),
            "STAGES": STAGES,
            "STAGE_BY_KEY": STAGE_BY_KEY,
            "GROUP_ORDER": GROUP_ORDER,
            "CAMPUSES": app.config["CAMPUSES"],
            "PLACES": app.config["PLACES"],
        }

    # Each of these says what happened in words rather than in a number, and
    # every one of them offers a way onward.
    @app.errorhandler(403)
    def _403(e):
        return render_template(
            "error.html", code=403, title="That page is not yours to open",
            detail="You are signed in, but this page belongs to a different "
                   "account. A department can only reach its own submission."), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template(
            "error.html", code=404, title="There is no page here",
            detail="The address may have been mistyped, or the page may have "
                   "moved since the link to it was made."), 404

    @app.errorhandler(413)
    def _413(e):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_template(
            "error.html", code=413, title="That file is too large",
            detail=f"The limit is {mb} MB per upload. Try a smaller scan, or "
                   f"split the document and upload it in parts."), 413

    @app.errorhandler(500)
    def _500(e):
        app.logger.exception("Unhandled error")
        # the Office sees what actually broke, so it can be reported and fixed;
        # a department never does
        why = ""
        if (session.get("user") or {}).get("role") == "admin":
            orig = getattr(e, "original_exception", None) or e
            why = f"{orig.__class__.__name__}: {orig}"[:600]
        return render_template(
            "error.html", code=500, title="Something went wrong at our end",
            detail="Nothing you had saved is lost — drafts are kept as you "
                   "type. Try again, and tell the Office of Academics if it "
                   "keeps happening.", why=why), 500

    return app
