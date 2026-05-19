import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-in-prod")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_CSRF_PROTECT = False  # enable in prod (requires HTTPS)

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
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
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_COOKIE_SECURE = False
    JWT_TOKEN_LOCATION = ["headers"]   # no cookies in tests
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
