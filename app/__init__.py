"""Application factory for the JAIN Office of Academics Data Portal."""

from __future__ import annotations

import logging

from flask import Flask, g, render_template, session

from config import Config

from . import db as database


def create_app(config_object=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object)

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

    @app.before_request
    def _load_user():
        g.user = session.get("user")

    @app.context_processor
    def _inject():
        from .schema import GROUP_ORDER, STAGES
        return {
            "current_user": session.get("user"),
            "app_settings": database.settings(),
            "STAGES": STAGES,
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
        return render_template(
            "error.html", code=500, title="Something went wrong at our end",
            detail="Nothing you had saved is lost — drafts are kept as you "
                   "type. Try again, and tell the Office of Academics if it "
                   "keeps happening."), 500

    return app
