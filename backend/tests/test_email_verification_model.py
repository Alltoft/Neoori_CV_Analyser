"""users carries whether its address is proven (email verification spec,
decisions 2 and 14).

The migration is loaded straight from its file and its backfill run on the
test database's own connection — there is no Alembic in the test run — the
same pattern as test_migration_erase_billets.py.
"""
import importlib.util
from datetime import datetime
from pathlib import Path

from app.extensions import db
from app.models.user import User

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "a9b0c1d2e3f4_email_verification.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("email_verification", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_new_user_is_unverified(app):
    user = User(email="new@test.fr", password_hash="x")
    db.session.add(user)
    db.session.commit()
    assert user.email_verified_at is None
    assert user.auth_mail_sent_at is None
    assert user.to_dict()["email_verified"] is False


def test_to_dict_reports_a_verified_user(app):
    user = User(email="v@test.fr", password_hash="x", email_verified_at=datetime.utcnow())
    db.session.add(user)
    db.session.commit()
    assert user.to_dict()["email_verified"] is True


def test_backfill_marks_existing_accounts_verified_at_their_signup(app):
    signed_up = datetime(2026, 9, 1, 12, 0, 0)
    already = datetime(2026, 9, 20, 8, 0, 0)
    old = User(email="old@test.fr", password_hash="x", created_at=signed_up)
    done = User(email="done@test.fr", password_hash="x", email_verified_at=already)
    db.session.add_all([old, done])
    db.session.commit()

    _migration().backfill(db.session.connection())
    db.session.commit()
    db.session.expire_all()

    assert db.session.get(User, old.id).email_verified_at == signed_up
    assert db.session.get(User, done.id).email_verified_at == already


def test_make_user_builds_a_login_ready_account(make_user):
    from app.extensions import bcrypt

    user = make_user(email="fixture@test.fr", password="motdepasse1", verified=False)
    assert bcrypt.check_password_hash(user.password_hash, "motdepasse1")
    assert user.email_verified_at is None
