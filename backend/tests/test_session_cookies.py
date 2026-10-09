"""One sign-in for every host (subdomain split spec, decisions 25–27)."""
from datetime import datetime

import pytest
from flask_jwt_extended import create_refresh_token

from app import create_app
from app.config import TestingConfig
from app.extensions import bcrypt, db
from app.models.user import User
from app.utils import auth_links


def _set_cookie(res, name: str) -> str:
    """The Set-Cookie line of one cookie."""
    return next(c for c in res.headers.getlist("Set-Cookie") if c.startswith(f"{name}="))


def _names(res) -> set[str]:
    return {c.split("=", 1)[0] for c in res.headers.getlist("Set-Cookie")}


def _user(email="marie@test.fr", password="motdepasse1") -> User:
    user = User(
        email=email, role="candidate", email_verified_at=datetime.utcnow(),
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()
    return user


def _login(client):
    return client.post("/api/auth/login", json={"email": "marie@test.fr", "password": "motdepasse1"})


@pytest.fixture
def dotted_app(monkeypatch):
    """An app built with a dotted DOMAIN. Built from scratch rather than by
    editing the shared fixture's config: create_app derives the cookie domain
    once, when it builds the app."""
    monkeypatch.setattr(TestingConfig, "DOMAIN", "neoori.test")
    application = create_app("testing")
    application.config["RESEND_API_KEY"] = None
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_the_session_cookies_have_new_names(app, client):
    _user()
    res = _login(client)
    assert res.status_code == 200
    assert {"neoori_access", "neoori_refresh"} <= _names(res)
    assert not {"access_token_cookie", "refresh_token_cookie"} & _names(res)


def test_a_single_label_domain_keeps_them_on_one_host(app, client):
    assert app.config["JWT_COOKIE_DOMAIN"] is None
    _user()
    res = _login(client)
    assert "Domain=" not in _set_cookie(res, "neoori_access")
    assert "Domain=" not in _set_cookie(res, "neoori_refresh")


def test_a_dotted_domain_puts_them_on_every_host(dotted_app):
    assert dotted_app.config["JWT_COOKIE_DOMAIN"] == "neoori.test"
    _user()
    res = _login(dotted_app.test_client())
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_access")
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_refresh")


def test_refresh_reissues_the_access_cookie_on_the_domain(dotted_app):
    user = _user()
    token = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    res = dotted_app.test_client().post(
        "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_access")


def test_logout_clears_the_session_everywhere_and_the_hold_on_its_host(dotted_app):
    # Review Focus 5: a tab left open on the other host is signed out at its
    # next request, because the cookies it would send are gone domain-wide.
    res = dotted_app.test_client().post("/api/auth/logout")
    assert res.status_code == 200
    for name in ("neoori_access", "neoori_refresh"):
        line = _set_cookie(res, name)
        assert "Domain=neoori.test" in line
        assert "Expires=Thu, 01 Jan 1970" in line
    assert "Domain=" not in _set_cookie(res, "neoori_hold")
