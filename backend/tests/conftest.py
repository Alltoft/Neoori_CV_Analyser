import sqlite3

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from flask_jwt_extended import create_access_token


@event.listens_for(Engine, "connect")
def _sqlite_enforce_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores FK constraints unless asked, so tests silently pass over
    violations MySQL would reject in production."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers(app):
    admin = User(
        email="admin@test.com",
        password_hash="x",
        role="admin",
        plan="free",
    )
    _db.session.add(admin)
    _db.session.commit()
    token = create_access_token(
        identity=str(admin.id),
        additional_claims={"role": "admin"},
    )
    return {"Authorization": f"Bearer {token}"}
