"""Verify, resend, forgot, reset (email verification spec, decisions 4–12
and 23)."""
import re
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_refresh_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _fresh(user):
    db.session.expire_all()
    return db.session.get(User, user.id)


def _verify(client, token, password="motdepasse1"):
    return client.post("/api/auth/verify-email", json={"token": token, "password": password})


def _reset(client, token, password="nouveau-mdp1"):
    return client.post("/api/auth/reset-password", json={"token": token, "password": password})


def _post_counting_mails(client, path, email, **extra):
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post(path, json={"email": email, **extra})
    return res, mock_send.call_count


# ── verify-email/check ────────────────────────────────────────────────────────

def test_check_names_the_address_of_a_live_link(client, make_user):
    user = make_user(verified=False)
    res = client.post("/api/auth/verify-email/check",
                      json={"token": auth_links.make_verify_token(user)})
    assert res.status_code == 200
    assert res.get_json() == {"email": user.email}


def test_check_says_expired(client, make_user, monkeypatch):
    token = auth_links.make_verify_token(make_user(verified=False))
    monkeypatch.setattr(auth_links, "VERIFY_MAX_AGE", -1)
    res = client.post("/api/auth/verify-email/check", json={"token": token})
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_expired"


# ── verify-email ──────────────────────────────────────────────────────────────

def test_link_and_password_verify_and_sign_in(client, make_user):
    user = make_user(verified=False)
    res = _verify(client, auth_links.make_verify_token(user, "/analyse/nouveau"))
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert res.get_json()["user"]["email_verified"] is True
    assert "neoori_access" in _cookies(res)
    assert _fresh(user).email_verified_at is not None


# safe_next lets these through because they are harmless used verbatim as a
# redirect target. Decoding, normalising or rebuilding them on the way back
# out would be what turns them into open redirects.
@pytest.mark.parametrize("stored", [
    "/%2F%2Fevil.com", "/analyse?x=a%20b&y=%2F", "/analyse?next=/..//evil.com",
])
def test_the_destination_comes_back_exactly_as_stored(client, make_user, stored):
    token = auth_links.make_verify_token(make_user(verified=False), stored)
    assert _verify(client, token).get_json()["next"] == stored


def test_the_wrong_password_changes_nothing(client, make_user):
    user = make_user(verified=False)
    res = _verify(client, auth_links.make_verify_token(user), "pasLeBon123")
    assert res.status_code == 401
    assert res.get_json()["code"] == "wrong_password"
    assert "neoori_access" not in _cookies(res)
    assert _fresh(user).email_verified_at is None


@pytest.mark.parametrize("password", ["é" * 40, "\ud800abc"])
def test_a_password_bcrypt_cannot_take_is_a_wrong_password(client, make_user, password):
    # 80 bytes, or a lone surrogate: bcrypt raised on both, a 500.
    user = make_user(verified=False)
    res = _verify(client, auth_links.make_verify_token(user), password)
    assert res.status_code == 401
    assert res.get_json()["code"] == "wrong_password"
    assert _fresh(user).email_verified_at is None


def test_a_second_use_is_a_login(client, make_user):
    token = auth_links.make_verify_token(make_user(verified=False))
    assert _verify(client, token).status_code == 200
    again = _verify(client, token)
    assert again.status_code == 200
    assert "neoori_access" in _cookies(again)


def test_a_link_for_an_address_the_account_no_longer_holds_is_invalid(client, make_user):
    user = make_user(verified=False)
    token = auth_links.make_verify_token(user)
    user.email = "autre@test.fr"
    db.session.commit()
    assert _verify(client, token).get_json()["code"] == "link_invalid"


def test_a_link_for_a_deleted_account_is_invalid(client, make_user):
    user = make_user(verified=False)
    token = auth_links.make_verify_token(user)
    db.session.delete(user)
    db.session.commit()
    res = _verify(client, token)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


def test_a_conseiller_without_next_lands_on_the_demande(client, make_user):
    user = make_user(verified=False)
    db.session.add(CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère", telephone="0561000000",
    ))
    db.session.commit()
    assert _verify(client, auth_links.make_verify_token(user)).get_json()["next"] == "/conseiller"


@pytest.mark.parametrize("suffix", [".", ")", "%29"])
def test_a_link_mangled_by_a_mail_client_is_invalid_not_a_crash(client, make_user, suffix):
    # Review Focus 2.
    res = _verify(client, auth_links.make_verify_token(make_user(verified=False)) + suffix)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


def test_a_password_with_surrounding_spaces_is_taken_verbatim(client, app):
    # Review Focus 3.
    password = "  espace devant et derrière  "
    assert client.post("/api/auth/register",
                       json={"email": "espaces@test.fr", "password": password}).status_code == 201
    user = User.query.filter_by(email="espaces@test.fr").one()
    token = auth_links.make_verify_token(user)
    assert _verify(client, token, password.strip()).status_code == 401
    assert _verify(client, token, password).status_code == 200


@pytest.mark.parametrize("body", [{"token": ["x"]}, {"token": {"a": 1}}, {"password": 42}, {}])
def test_hostile_verify_bodies_answer_400(client, body):
    res = client.post("/api/auth/verify-email", json=body)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


# ── resend-verification ───────────────────────────────────────────────────────

def test_resend_answers_the_same_whatever_the_account(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="attente@test.fr", verified=False)
    make_user(email="actif@test.fr")
    bodies, sent = set(), {}
    for email in ("attente@test.fr", "actif@test.fr", "inconnu@test.fr"):
        res, count = _post_counting_mails(client, "/api/auth/resend-verification", email)
        assert res.status_code == 200
        bodies.add(res.get_data())
        sent[email] = count
    assert len(bodies) == 1
    assert sent == {"attente@test.fr": 1, "actif@test.fr": 0, "inconnu@test.fr": 0}


def test_resend_finds_the_account_whatever_the_case_and_padding(client, app, make_user):
    # Review Focus 1.
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="marie@test.fr", verified=False)
    _res, count = _post_counting_mails(client, "/api/auth/resend-verification", "  Marie@Test.FR ")
    assert count == 1


def test_resend_keeps_the_destination_in_the_new_link(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="attente@test.fr", verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        client.post("/api/auth/resend-verification",
                    json={"email": "attente@test.fr", "next": "/analyse/nouveau"})
    token = TOKEN.search(mock_send.call_args[0][0]["text"]).group(1)
    assert auth_links.load_verify_token(token).payload["next"] == "/analyse/nouveau"


@pytest.mark.parametrize("path", ["/api/auth/resend-verification", "/api/auth/forgot-password"])
@pytest.mark.parametrize("body", [{}, {"email": 42}, {"email": ["a@test.fr"]}, {"email": "   "}])
def test_hostile_email_bodies_get_the_ordinary_answer(client, app, path, body):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post(path, json=body)
    assert res.status_code == 200
    assert mock_send.call_count == 0


# ── forgot-password ───────────────────────────────────────────────────────────

def test_forgot_answers_the_same_whatever_the_account(client, app, make_user):
    # Verified, unverified and unknown must be indistinguishable from outside:
    # the unverified one is the state a stranger must not be able to probe for.
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="actif@test.fr")
    make_user(email="attente@test.fr", verified=False)
    answers, sent = set(), {}
    for email in ("actif@test.fr", "attente@test.fr", "inconnu@test.fr"):
        res, count = _post_counting_mails(client, "/api/auth/forgot-password", email)
        answers.add((res.status_code, res.get_data()))
        sent[email] = count
    assert len(answers) == 1
    assert next(iter(answers))[0] == 200
    assert sent == {"actif@test.fr": 1, "attente@test.fr": 1, "inconnu@test.fr": 0}


def test_forgot_finds_the_account_whatever_the_case_and_padding(client, app, make_user):
    # Review Focus 1.
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="marie@test.fr")
    _res, count = _post_counting_mails(client, "/api/auth/forgot-password", " MARIE@test.fr")
    assert count == 1


# ── reset-password ────────────────────────────────────────────────────────────

def test_reset_sets_the_password_and_signs_in(client, make_user):
    user = make_user(email="reset@test.fr")
    res = _reset(client, auth_links.make_reset_token(user))
    assert res.status_code == 200
    assert "neoori_access" in _cookies(res)
    login = client.post("/api/auth/login", json={"email": "reset@test.fr", "password": "nouveau-mdp1"})
    assert login.status_code == 200


def test_a_reset_link_works_once(client, make_user):
    token = auth_links.make_reset_token(make_user())
    assert _reset(client, token).status_code == 200
    second = _reset(client, token, "encore-autre1")
    assert second.status_code == 400
    assert second.get_json()["code"] == "link_invalid"


def test_a_short_password_does_not_spend_the_link(client, make_user):
    token = auth_links.make_reset_token(make_user())
    assert _reset(client, token, "court").status_code == 400
    assert _reset(client, token).status_code == 200


@pytest.mark.parametrize("password", ["é" * 40, "\ud800abcdefgh"])
def test_a_password_bcrypt_cannot_take_does_not_spend_the_link(client, make_user, password):
    token = auth_links.make_reset_token(make_user())
    res = _reset(client, token, password)
    assert res.status_code == 400
    assert res.get_json()["error"].startswith("Le mot de passe")
    assert _reset(client, token).status_code == 200


def test_a_reset_proves_the_inbox(client, make_user):
    user = make_user(verified=False)
    assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    assert _fresh(user).email_verified_at is not None


def test_a_reset_ends_sessions_opened_under_the_old_password(client, make_user):
    user = make_user()
    old = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    res = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {old}"})
    assert res.status_code == 401


def test_an_expired_reset_link_says_so(client, make_user, monkeypatch):
    token = auth_links.make_reset_token(make_user())
    monkeypatch.setattr(auth_links, "RESET_MAX_AGE", -1)
    assert _reset(client, token).get_json()["code"] == "link_expired"


def test_a_reset_keeps_surrounding_spaces(client, make_user):
    # Review Focus 3.
    user = make_user(email="sp@test.fr")
    assert _reset(client, auth_links.make_reset_token(user), "  avec espaces  ").status_code == 200
    login = client.post("/api/auth/login", json={"email": "sp@test.fr", "password": "  avec espaces  "})
    assert login.status_code == 200


# ── the password-changed notice ──────────────────────────────────────────────

def test_a_reset_tells_the_address_the_password_changed(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="reset@test.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    mock_send.assert_called_once()
    mail = mock_send.call_args[0][0]
    assert mail["to"] == ["reset@test.fr"]
    assert mail["subject"] == "Votre mot de passe a été modifié"
    # A notice, not an account mail: the one-a-minute clock is not touched.
    assert _fresh(user).auth_mail_sent_at is None


def test_a_refused_reset_sends_no_notice(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    token = auth_links.make_reset_token(make_user())
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert _reset(client, token, "court").status_code == 400      # password refused
        assert _reset(client, "pas-un-lien").status_code == 400       # dead link
    mock_send.assert_not_called()


def test_a_reset_survives_a_mail_outage(client, app, make_user):
    # Review Focus 4: the password changes and the session opens anyway.
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="reset@test.fr")
    with patch(SEND, side_effect=RuntimeError("resend down")):
        res = _reset(client, auth_links.make_reset_token(user))
    assert res.status_code == 200
    assert "neoori_access" in _cookies(res)
