import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _addresses(raw: str) -> list[str]:
    """A comma-separated env value as clean, lowercased email addresses."""
    return [a.strip().lower() for a in raw.split(",") if a.strip()]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # TiDB Cloud closes idle connections; without pre-ping the first request
    # after an idle period hits a stale pooled connection and 500s.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-in-prod")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = "Lax"    # browser → Next.js proxy → Flask; always same-origin from browser POV
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_CSRF_PROTECT = False

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    # Resend refuses a From on an unverified domain, so neoori.tech must carry
    # the DNS records before the first mail goes out.
    MAIL_FROM = os.environ.get("MAIL_FROM", "neoori <bonjour@neoori.tech>")
    # Public origin every account mail links to (verification, reset,
    # conseiller). The dev compose file points it at http://localhost:8080.
    APP_URL = os.environ.get("APP_URL", "https://neoori.tech").rstrip("/")
    # Who the « Nouvelle demande de compte conseiller » mail goes to, comma-
    # separated. Production names a real inbox: the shared admin login
    # (admin@neoori.dev) has no mailbox. Unset, every verified admin gets it.
    ADMIN_NOTIFY_EMAILS = _addresses(os.environ.get("ADMIN_NOTIFY_EMAIL", ""))
    # « Continuer avec Google / Microsoft » (social sign-in spec, decision 13):
    # a provider's button shows only once both its keys are set.
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET")
    # Authlib keeps the OAuth state, PKCE verifier and nonce in Flask's
    # session cookie between /start and /callback. Lax: the provider sends
    # the browser back with a top-level GET, which carries it.
    SESSION_COOKIE_SAMESITE = "Lax"
    FRONTEND_ORIGINS = [
        o.strip()
        for o in os.environ.get("FRONTEND_URL", "http://localhost:3000,http://localhost:3001").split(",")
        if o.strip()
    ]

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB — CV PDF cap


class DevelopmentConfig(Config):
    DEBUG = True
    JWT_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True   # required for SameSite=None
    SESSION_COOKIE_SECURE = True   # the OAuth state cookie, and the signup ticket


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_COOKIE_SECURE = False
    JWT_TOKEN_LOCATION = ["headers"]   # no cookies in tests
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    # Real bcrypt hashes in tests (login and verify-email check them), at the
    # cheapest cost: the default 12 rounds would add seconds per test.
    BCRYPT_LOG_ROUNDS = 4


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
