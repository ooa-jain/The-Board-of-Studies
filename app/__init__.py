"""Application factory for the JAIN OoA BoS Data Repository Portal."""

from __future__ import annotations

import logging

from flask import Flask, g, render_template, request, session

from config import Config

from . import db as database
from . import security


def create_app(config_object=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object)

    logging.basicConfig(
        level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
    )

    app.config["UPLOAD_ROOT"].mkdir(parents=True, exist_ok=True)

    database.init_db(app)
    security.protect(app)

    from .auth import bp as auth_bp
    from .admin import bp as admin_bp
    from .dept import bp as dept_bp
    from .public import bp as public_bp
    from .testmode import bp as test_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(dept_bp, url_prefix="/department")
    # Registered either way; every route inside it answers 404 unless test
    # mode is on, so url_for keeps working and the templates stay simple.
    app.register_blueprint(test_bp, url_prefix="/test")

    if app.config.get("TEST_MODE"):
        app.logger.warning("TEST MODE IS ON — passwordless sign-in is available at /test. "
                           "Never run the live portal this way.")

    @app.before_request
    def _load_user():
        g.user = session.get("user")

    @app.context_processor
    def _inject():
        from .public import home_url_for
        from .schema import GROUP_ORDER, STAGES
        user = session.get("user")
        return {
            "current_user": user,
            "app_settings": database.settings(),
            "STAGES": STAGES,
            "GROUP_ORDER": GROUP_ORDER,
            "CAMPUSES": app.config["CAMPUSES"],
            "TEST_MODE": bool(app.config.get("TEST_MODE")),
            # Where the masthead and the error pages point. For someone signed
            # in that is their own dashboard, not the public introduction.
            "home_url": home_url_for(user),
            "current_path": request.path,
        }

    def _error(code, message, template="error.html"):
        return render_template(template, code=code, message=message), code

    @app.errorhandler(400)
    def _400(e):
        return _error(400, getattr(e, "description", None)
                      or "That request could not be processed. Reload the page and try again.")

    @app.errorhandler(403)
    def _403(e):
        return _error(403, "You do not have access to that page.")

    @app.errorhandler(404)
    def _404(e):
        return _error(404, "That page does not exist.")

    @app.errorhandler(413)
    def _413(e):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return _error(413, f"That file is too large. The limit is {mb} MB.")

    @app.errorhandler(500)
    def _500(e):
        app.logger.exception("Unhandled error")
        return _error(500, "Something went wrong at our end. "
                           "The Office of Academics has been notified.")

    return app
