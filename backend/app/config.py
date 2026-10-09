import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _addresses(raw: str) -> list[str]:
    """A comma-separated env value as clean, lowercased email addresses."""
    return [a.strip().lower() for a in raw.split(",") if a.strip()]


def _domain(raw: str) -> str:
    """DOMAIN as the code compares it: trimmed, lowercased, no trailing dot.
    Blank is localhost, like the frontend's fallback (lib/site.ts)."""
    return raw.strip().lower().rstrip(".") or "localhost"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # MySQL closes connections idle past wait_timeout; without pre-ping the
    # first request after an idle period hits a stale pooled connection and
    # 500s.
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
    # Subdomain split spec, decision 25: one session for every host. The
    # cookies carry Domain=DOMAIN (create_app sets JWT_COOKIE_DOMAIN from
    # site.cookie_domain), under new names: browsers still hold the old
    # host-only `access_token_cookie` on the root, and under the same name the
    # root would receive two cookies and Flask would read whichever came
    # first. frontend/src/lib/sign-in-gate.ts SESSION_COOKIE names the access
    # cookie too: keep the two in step.
    JWT_ACCESS_COOKIE_NAME = "neoori_access"
    JWT_REFRESH_COOKIE_NAME = "neoori_refresh"

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    # Resend refuses a From on an unverified domain, so neoori.tech must carry
    # the DNS records before the first mail goes out. Not derived from DOMAIN
    # on purpose (subdomain split spec, decision 23): a refused mail fails
    # silently, so a domain swap would quietly stop every mail. Verify the new
    # domain in Resend first, then change this.
    MAIL_FROM = os.environ.get("MAIL_FROM", "neoori <bonjour@neoori.tech>")
    # The base domain, written here and nowhere else (subdomain split spec,
    # decision 19). The app answers on DOMAIN (the landing), cv.DOMAIN and
    # voyage.DOMAIN; app/utils/site.py builds every absolute URL from it.
    # nginx and the frontend read the same line of /srv/neoori/.env.
    DOMAIN = _domain(os.environ.get("DOMAIN", ""))
    # Dev only (decision 20): the local stack is http on :8080. Production
    # sets neither.
    PUBLIC_SCHEME = os.environ.get("PUBLIC_SCHEME", "").strip() or "https"
    PUBLIC_PORT = os.environ.get("PUBLIC_PORT", "").strip()
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
    # The Flask session only carries the OAuth state between
    # /api/auth/<provider>/start and /callback; nothing else uses it, so it
    # need not ride on every page and asset request.
    SESSION_COOKIE_PATH = "/api/auth"
    FRONTEND_ORIGINS = [
        o.strip()
        for o in os.environ.get("FRONTEND_URL", "http://localhost:3000,http://localhost:3001").split(",")
        if o.strip()
    ]

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB — CV PDF cap

    # Four-doors spec: the client input caps (decision 37), the daily caps on
    # free runs (decision 40), and how long ownerless rows live (decisions 12,
    # 29, 35). All overridable from /srv/neoori/.env.
    CV_TEXT_MAX = int(os.environ.get("CV_TEXT_MAX", "40000"))
    # Ownerless drafts alive at once (48 h window), all addresses together:
    # each holds up to ~50 KB, and nginx alone would let one address write
    # ~14 000 a day (spec decision 40).
    HELD_DRAFTS_MAX = int(os.environ.get("HELD_DRAFTS_MAX", "2000"))
    CIBLE_MAX = int(os.environ.get("CIBLE_MAX", "10000"))
    ANONYMOUS_RUNS_PER_DAY = int(os.environ.get("ANONYMOUS_RUNS_PER_DAY", "200"))
    FREE_RUNS_PER_ACCOUNT_PER_DAY = int(os.environ.get("FREE_RUNS_PER_ACCOUNT_PER_DAY", "5"))
    ANONYMOUS_RETENTION_DAYS = int(os.environ.get("ANONYMOUS_RETENTION_DAYS", "30"))
    ADVISOR_RETENTION_DAYS = int(os.environ.get("ADVISOR_RETENTION_DAYS", "365"))
    HELD_DRAFT_RETENTION_HOURS = int(os.environ.get("HELD_DRAFT_RETENTION_HOURS", "48"))


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
    # Whatever a developer's .env says. Single-label on purpose: the session
    # cookies stay host-only (spec decision 26), so the test client's cookie
    # jar, which runs on localhost, keeps working. A test that needs the
    # Domain attribute builds an app with a dotted DOMAIN itself.
    DOMAIN = "localhost"
    PUBLIC_SCHEME = "https"
    PUBLIC_PORT = ""


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
