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


@pytest.fixture(autouse=True)
def _no_live_anthropic_key(monkeypatch):
    """Make a forgotten mock fail loudly instead of billing the real account.

    create_app() calls load_dotenv(), so a developer's real ANTHROPIC_API_KEY is
    on os.environ for the whole run. Test isolation then rests on every test
    remembering to patch the client -- and _get_client() reads the key at call
    time, so the one that forgets makes a real, paid API call and the suite
    still passes. Blanking the key turns that into an error at the boundary.

    The SDK still *constructs* a client from an empty key -- it only rejects at
    request time -- so this does not fail at the boundary. What it guarantees is
    the thing that matters: an unpatched call gets a 401 instead of a billed
    completion. Verified, not assumed.

    Autouse and unconditional: a test that genuinely wants a key must set one
    itself, which is a visible act rather than an inherited accident.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


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
