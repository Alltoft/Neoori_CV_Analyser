"""The two tables social sign-in adds (social sign-in spec, decisions 2
and 4)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.login_link import LoginLink


def test_one_provider_account_opens_one_neoori_account(app, make_user):
    marie = make_user(email="marie@test.fr")
    paul = make_user(email="paul@test.fr")
    db.session.add(AuthIdentity(user_id=marie.id, provider="google", subject="1234"))
    db.session.commit()
    db.session.add(AuthIdentity(user_id=paul.id, provider="google", subject="1234"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_the_same_subject_at_another_provider_is_another_identity(app, make_user):
    marie = make_user()
    db.session.add_all([
        AuthIdentity(user_id=marie.id, provider="google", subject="1234"),
        AuthIdentity(user_id=marie.id, provider="microsoft", subject="1234"),
    ])
    db.session.commit()
    assert AuthIdentity.query.filter_by(user_id=marie.id).count() == 2


def test_erasing_an_account_erases_its_identities(app, make_user):
    marie = make_user()
    db.session.add(AuthIdentity(user_id=marie.id, provider="google", subject="1234"))
    db.session.commit()
    db.session.delete(marie)
    db.session.commit()
    assert AuthIdentity.query.count() == 0


def test_a_login_link_row_keeps_no_address(app):
    columns = {c.name for c in LoginLink.__table__.columns}
    assert columns == {"id", "email_hash", "created_at", "used_at"}
