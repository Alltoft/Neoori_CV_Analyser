"""No session for an unproven address (email verification spec, decisions
2, 6, 9 and 10)."""
import re
from unittest.mock import patch

import pytest
from flask import jsonify
from flask_jwt_extended import create_refresh_token

from app.extensions import bcrypt, db
from app.models.user import User
from app.routes.auth import _issue_session
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _register(client, email="nouveau@test.fr", password="motdepasse1", **extra):
    return client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def _login(client, email, password="motdepasse1"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _refresh(client, token):
    return client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})


def _refresh_token(user):
    return create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )


def test_register_opens_no_session(client, app):
    app.debug = False   # FLASK_DEBUG in a developer's shell must not flip mail_sent
    res = _register(client)
    assert res.status_code == 201
    assert "access_token_cookie" not in _cookies(res)
    assert res.get_json()["user"]["email_verified"] is False
    assert res.get_json()["mail_sent"] is False      # no key in tests


def test_register_mails_a_link_that_keeps_the_destination(client, app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = _register(client, next="/analyse/nouveau")
    assert res.get_json()["mail_sent"] is True
    token = TOKEN.search(mock_send.call_args[0][0]["text"]).group(1)
    assert auth_links.load_verify_token(token).payload["next"] == "/analyse/nouveau"


@pytest.mark.parametrize("verified", [True, False])
def test_register_never_overwrites_an_existing_account(client, make_user, verified):
    user = make_user(email="pris@test.fr", verified=verified)
    before = user.password_hash
    res = _register(client, email="pris@test.fr", password="autrechose9")
    assert res.status_code == 409
    db.session.expire_all()
    assert db.session.get(User, user.id).password_hash == before


def test_login_of_an_unverified_account_says_so_only_with_the_right_password(client, make_user):
    make_user(email="attente@test.fr", verified=False)
    wrong = _login(client, "attente@test.fr", "pasLeBon123")
    assert wrong.status_code == 401
    assert wrong.get_json()["error"] == "Identifiants incorrects."
    right = _login(client, "attente@test.fr")
    assert right.status_code == 403
    assert right.get_json()["code"] == "email_unverified"
    assert "access_token_cookie" not in _cookies(right)


def test_login_of_a_verified_account_opens_a_session(client, make_user):
    make_user(email="ok@test.fr")
    res = _login(client, "ok@test.fr")
    assert res.status_code == 200
    assert "access_token_cookie" in _cookies(res)
    assert "refresh_token_cookie" in _cookies(res)


def test_issue_session_refuses_an_unverified_account(app, make_user):
    with pytest.raises(ValueError):
        _issue_session(jsonify({}), make_user(verified=False))


def test_refresh_works_under_the_password_it_was_minted_with(client, make_user):
    assert _refresh(client, _refresh_token(make_user())).status_code == 200


def test_refresh_without_pwv_is_refused(client, make_user):
    user = make_user()
    assert _refresh(client, create_refresh_token(identity=user.id)).status_code == 401


def test_refresh_after_a_password_change_is_refused(client, make_user):
    user = make_user()
    token = _refresh_token(user)
    user.password_hash = bcrypt.generate_password_hash("nouveau-mdp1").decode("utf-8")
    db.session.commit()
    assert _refresh(client, token).status_code == 401


def test_refresh_of_an_unverified_account_is_refused(client, make_user):
    assert _refresh(client, _refresh_token(make_user(verified=False))).status_code == 401
