import os
from flask import Flask
from .config import config
from .extensions import db, migrate, jwt, bcrypt, cors


def create_app(env: str | None = None) -> Flask:
    env = env or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config.get(env, config["default"]))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/.*": {"origins": app.config["FRONTEND_ORIGINS"]}},
        supports_credentials=True,  # required for httpOnly cookie auth
    )

    # Models must be imported before migrate can detect them
    from .models import user, analysis, prompt_version, counselor_note, counselor_code  # noqa: F401

    # Blueprints
    from .routes.auth import auth_bp
    from .routes.analyses import analyses_bp
    from .routes.prompts import prompts_bp
    from .routes.upload import upload_bp
    from .routes.admin import admin_bp
    from .routes.counselor import counselor_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(analyses_bp, url_prefix="/api/analyses")
    app.register_blueprint(prompts_bp, url_prefix="/api/prompts")
    app.register_blueprint(upload_bp, url_prefix="/api/upload")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(counselor_bp, url_prefix="/api/c")

    @app.route("/api/health")
    def health():
        return {"status": "ok"}, 200

    # Reset analyses that were mid-stream when the server last shut down
    with app.app_context():
        try:
            from .models.analysis import Analysis
            stale = Analysis.query.filter_by(status="running").update({"status": "error"})
            db.session.commit()
            if stale:
                app.logger.info(f"Startup: reset {stale} stale running analysis/analyses to error.")
        except Exception:
            pass  # DB not yet migrated on first boot

    return app
