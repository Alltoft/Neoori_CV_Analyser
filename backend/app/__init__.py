import os
from datetime import datetime, timedelta

from flask import Flask
from .config import config
from .extensions import db, migrate, jwt, bcrypt, cors

# How long a row may sit in 'running' before a restart is allowed to call it
# orphaned. Must stay above the longest plausible generation (paid tier at
# 8000 tokens runs a couple of minutes) — see reap_stale_running().
STALE_RUN_CUTOFF_MINUTES = int(os.getenv("STALE_RUN_CUTOFF_MINUTES", "15"))


def reap_stale_running(cutoff_minutes: int | None = None) -> int:
    """Reset analyses orphaned mid-stream by a previous process. Returns the count.

    Requires an app context. Only rows older than the cutoff are touched:
    create_app() runs in *every* process that opens this database — each
    gunicorn worker, `flask db upgrade` on deploy, every seed or admin
    script — so resetting all 'running' rows reaches analyses that are
    still streaming. The candidate's page then shows « L'analyse n'a pas
    abouti » and stops polling, while the background thread finishes and
    writes 'success' to a row nobody is watching any more.
    """
    from .models.analysis import Analysis

    cutoff = datetime.utcnow() - timedelta(
        minutes=STALE_RUN_CUTOFF_MINUTES if cutoff_minutes is None else cutoff_minutes
    )
    stale = (
        Analysis.query
        .filter(Analysis.status == "running", Analysis.created_at < cutoff)
        .update({"status": "error"}, synchronize_session=False)
    )
    db.session.commit()
    return stale


def reap_stale_generating(cutoff_minutes: int | None = None) -> int:
    """Reset voyages orphaned mid-generation by a previous process.

    Same rationale as reap_stale_running() and the same cutoff: create_app()
    runs in every process that opens this database, so resetting all
    'generating' rows would reach voyages that are still streaming.

    updated_at is the right clock: the route commits the 'generating' status
    before spawning the thread, which bumps it.

    Both statuses are swept in ONE statement, each rewritten only where it
    actually reads 'generating'. Two successive UPDATEs would not do: the first
    bumps updated_at through the column's own onupdate, pushing the row past
    the cutoff, so the second would no longer match it — and a voyage that was
    generating both a phrase and a portrait would stay stranded on the second
    status, which is the exact failure this reaps.

    Nothing writes an `error` payload here. No thread was alive to observe the
    failure, so the status is the whole signal; inventing a message would claim
    knowledge of something nobody saw.
    """
    from .models.voyage import Voyage

    cutoff = datetime.utcnow() - timedelta(
        minutes=STALE_RUN_CUTOFF_MINUTES if cutoff_minutes is None else cutoff_minutes
    )
    stale = (
        Voyage.query
        .filter(
            db.or_(
                Voyage.micro_status == "generating",
                Voyage.portrait_status == "generating",
            ),
            Voyage.updated_at < cutoff,
        )
        .update(
            {
                Voyage.micro_status: db.case(
                    (Voyage.micro_status == "generating", "error"),
                    else_=Voyage.micro_status,
                ),
                Voyage.portrait_status: db.case(
                    (Voyage.portrait_status == "generating", "error"),
                    else_=Voyage.portrait_status,
                ),
            },
            synchronize_session=False,
        )
    )
    db.session.commit()
    return stale


def create_app(env: str | None = None) -> Flask:
    env = env or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config.get(env, config["default"]))
    app.url_map.strict_slashes = False

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
    from .models import user, analysis, prompt_version, counselor_note, counselor_code, profile, price_feedback, voyage  # noqa: F401

    # Blueprints
    from .routes.auth import auth_bp
    from .routes.analyses import analyses_bp
    from .routes.prompts import prompts_bp
    from .routes.upload import upload_bp
    from .routes.admin import admin_bp
    from .routes.counselor import counselor_bp
    from .routes.profile import profile_bp
    from .routes.voyage import voyage_bp
    from .routes.payments import payments_bp

    app.register_blueprint(payments_bp, url_prefix="/api/payments")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(analyses_bp, url_prefix="/api/analyses")
    app.register_blueprint(prompts_bp, url_prefix="/api/prompts")
    app.register_blueprint(upload_bp, url_prefix="/api/upload")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(counselor_bp, url_prefix="/api/c")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(voyage_bp, url_prefix="/api/voyage")

    @app.route("/api/health")
    def health():
        return {"status": "ok"}, 200

    def _cors_error_response(body: dict, status: int):
        from flask import jsonify, request
        origin = request.headers.get("Origin", "")
        resp = jsonify(body)
        resp.status_code = status
        if origin in app.config["FRONTEND_ORIGINS"]:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    @jwt.unauthorized_loader
    def missing_token(_err):
        return _cors_error_response({"error": "Non authentifié."}, 401)

    @jwt.invalid_token_loader
    def invalid_token(_err):
        return _cors_error_response({"error": "Token invalide."}, 422)

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_data):
        return _cors_error_response({"error": "Session expirée."}, 401)

    @jwt.needs_fresh_token_loader
    def needs_fresh(_jwt_header, _jwt_data):
        return _cors_error_response({"error": "Token non récent."}, 401)

    @jwt.revoked_token_loader
    def revoked_token(_jwt_header, _jwt_data):
        return _cors_error_response({"error": "Token révoqué."}, 401)

    # Reset analyses and voyages that were mid-generation when the server last
    # shut down
    # One try each, deliberately: sharing one meant a failure in the analyses
    # sweep skipped the voyage sweep for that whole boot, and a stranded voyage
    # has no error state for the person to see -- the hub just polls it for ever.
    with app.app_context():
        try:
            stale = reap_stale_running()
            if stale:
                app.logger.info(f"Startup: reset {stale} stale running analysis/analyses to error.")
        except Exception:
            pass  # DB not yet migrated on first boot
        try:
            stranded = reap_stale_generating()
            if stranded:
                app.logger.info(f"Startup: reset {stranded} stale generating voyage(s) to error.")
        except Exception:
            pass  # DB not yet migrated on first boot

    return app
