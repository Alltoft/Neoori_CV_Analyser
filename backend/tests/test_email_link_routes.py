"""« Recevoir un lien de connexion » end to end (social sign-in spec,
decisions 14–17)."""
import re
from datetime import datetime
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.login_link import LoginLink
from app.models.profile import CONSENT_VERSION, Profile
from app.models.user import User
from app.routes import auth_link
from app.routes.auth import password_matches
from app.services import sign_in
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _request_link(client, app, email="marie@test.fr", **extra):
    """POST /email-link with a working mail provider: (response, token or None)."""
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post("/api/auth/email-link", json={"email": email, **extra})
    token = TOKEN.search(mock_send.call_args[0][0]["text"]).group(1) if mock_send.called else None
    return res, token


def _check(client, token):
    return client.post("/api/auth/email-link/check", json={"token": token})


def _consume(client, token):
    return client.post("/api/auth/email-link/consume", json={"token": token})


# ── send ──────────────────────────────────────────────────────────────────────

def test_the_answer_does_not_say_whether_an_account_exists(client, app, make_user):
    make_user(email="compte@test.fr")
    with_account, _ = _request_link(client, app, "compte@test.fr")
    without, _ = _request_link(client, app, "personne@test.fr")
    assert with_account.status_code == without.status_code == 200
    assert with_account.get_json() == without.get_json() == {"mail_sent": True}


@pytest.mark.parametrize("email", ["", "pas-une-adresse", None, 42, "a@b"])
def test_a_malformed_address_is_refused(client, email):
    res = client.post("/api/auth/email-link", json={"email": email})
    assert res.status_code == 400
    assert res.get_json()["error"] == "Email invalide."


def test_an_address_typed_with_capitals_and_spaces_is_paced_as_one(client, app):
    _request_link(client, app, "marie@test.fr")
    _, token = _request_link(client, app, "  Marie@Test.FR ")
    assert token is None                 # inside the minute: no second mail
    assert LoginLink.query.count() == 1


def test_an_address_typed_with_capitals_and_spaces_signs_in_its_account(client, app, make_user):
    # The test above cannot tell a stripped address from a refused one: a
    # spaced address fails the shape check, and no mail leaves either way.
    # Here the mail must leave and name the stored address, so both the strip
    # and the lowercase have to happen in the send path.
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app, "  MARIE@Test.FR ")
    assert _consume(client, token).get_json()["user"]["email"] == "marie@test.fr"


def test_the_destination_rides_in_the_link(client, app):
    _, token = _request_link(client, app, next="/analyse/nouveau")
    assert auth_links.load_login_token(token).payload["next"] == "/analyse/nouveau"


def test_a_lookalike_row_neither_greets_nor_is_paced(client, app, make_user, monkeypatch):
    lookalike = make_user(email="marie@gmaïl.com")
    db.session.add(Profile(user_id=lookalike.id, prenom="Squatteur",
                           consent_at=datetime.utcnow(), consent_version=CONSENT_VERSION))
    db.session.commit()
    asked = []
    monkeypatch.setattr(sign_in, "_account_at", lambda email: asked.append(email) or lookalike)
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        client.post("/api/auth/email-link", json={"email": "marie@gmail.com"})
    # SQLite finds no row for « marie@gmail.com » by itself, so without this
    # the test would pass even if the route skipped account_of altogether.
    assert asked == ["marie@gmail.com"]
    assert mock_send.call_args[0][0]["text"].startswith("Bonjour,")
    assert db.session.get(User, lookalike.id).auth_mail_sent_at is None


def test_two_addresses_are_paced_apart(client, app):
    # Closes a gap Task 5's review found: dropping the email_hash filter from
    # the pacing query passed every test, and would let one request silence
    # every other address for a minute.
    _, first = _request_link(client, app, "marie@test.fr")
    _, second = _request_link(client, app, "paul@test.fr")
    assert first is not None and second is not None
    assert LoginLink.query.count() == 2


# ── check ─────────────────────────────────────────────────────────────────────

def test_check_names_the_address_and_spends_nothing(client, app):
    _, token = _request_link(client, app)
    for _ in range(2):
        res = _check(client, token)
        assert res.status_code == 200 and res.get_json() == {"email": "marie@test.fr"}
    assert LoginLink.query.one().used_at is None


def test_check_says_expired(client, app, monkeypatch):
    _, token = _request_link(client, app)
    monkeypatch.setattr(auth_links, "LOGIN_MAX_AGE", -1)
    res = _check(client, token)
    assert res.status_code == 400 and res.get_json()["code"] == "link_expired"


# ── consume ───────────────────────────────────────────────────────────────────

def test_a_link_for_an_account_signs_it_in(client, app, make_user):
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app, next="/analyse/nouveau")
    res = _consume(client, token)
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert res.get_json()["user"]["email"] == "marie@test.fr"
    assert "access_token_cookie" in _cookies(res)


def test_a_link_is_single_use(client, app, make_user):
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app)
    assert _consume(client, token).status_code == 200
    again = _consume(client, token)
    assert again.status_code == 400 and again.get_json()["code"] == "link_invalid"
    assert _check(client, token).get_json()["code"] == "link_invalid"


def test_two_clicks_racing_spend_the_link_once(client, app, make_user, monkeypatch):
    # Both clicks pass the liveness read; only the UPDATE can tell them apart.
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app)
    payload = auth_links.load_login_token(token).payload
    monkeypatch.setattr(auth_link, "_live_link", lambda t: (payload, None))
    assert _consume(client, token).status_code == 200
    second = _consume(client, token)
    assert second.status_code == 400 and second.get_json()["code"] == "link_invalid"


def test_spending_one_link_leaves_another_live(client, app):
    # The claim names its own row. Without the id filter, one consume would
    # spend every unused link, and with two of them waiting would refuse itself.
    _, marie = _request_link(client, app, "marie@test.fr")
    _, paul = _request_link(client, app, "paul@test.fr")
    assert _consume(client, marie).status_code == 200
    assert _check(client, paul).status_code == 200


def test_a_tampered_link_is_invalid(client, app):
    _, token = _request_link(client, app)
    res = _consume(client, token + "x")
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"


def test_a_signed_link_without_its_row_is_invalid(client, app):
    # e.g. a link minted while the mail failed: no row was ever written.
    token = auth_links.make_login_token("never-written", "marie@test.fr")
    assert _consume(client, token).get_json()["code"] == "link_invalid"


def test_an_address_without_an_account_goes_on_to_finalise(client, app):
    _, token = _request_link(client, app, next="/analyse/nouveau")
    res = _consume(client, token)
    assert res.status_code == 200 and res.get_json() == {"signup": True}
    assert "access_token_cookie" not in _cookies(res)
    assert User.query.count() == 0      # decision 1: no account before consent
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value
    ).payload
    assert ticket == {"method": "email", "sub": None, "email": "marie@test.fr",
                      "prenom_hint": "", "next": "/analyse/nouveau"}


def test_a_link_that_hands_out_a_ticket_is_spent(client, app):
    # Spent on this path too: otherwise anyone holding the link could replay it
    # once the person had finalised, find the new account, and get a session.
    _, token = _request_link(client, app)
    assert _consume(client, token).get_json() == {"signup": True}
    again = _consume(client, token)
    assert again.status_code == 400 and again.get_json()["code"] == "link_invalid"


def test_a_link_to_an_unverified_account_applies_ruling_4(client, app, make_user):
    user = make_user(email="marie@test.fr", verified=False)
    _, token = _request_link(client, app)
    assert _consume(client, token).status_code == 200
    db.session.expire_all()
    fresh = db.session.get(User, user.id)
    assert fresh.email_verified_at is not None
    assert not password_matches(fresh, "motdepasse1")


def test_a_conseiller_without_next_lands_on_the_demande(client, app, make_user):
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    _, token = _request_link(client, app, "claire@capemploi.fr")
    assert _consume(client, token).get_json()["next"] == "/conseiller"


def test_a_link_to_an_address_held_by_a_lookalike_is_refused(client, app, make_user, monkeypatch):
    lookalike = make_user(email="marie@gmaïl.com", verified=False)
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    _, token = _request_link(client, app, "marie@gmail.com")
    res = _consume(client, token)
    assert res.status_code == 409 and res.get_json()["code"] == "address_unavailable"
    assert client.get_cookie("signup_ticket", path="/api/auth") is None
    db.session.expire_all()
    assert db.session.get(User, lookalike.id).email_verified_at is None
    assert _consume(client, token).get_json()["code"] == "link_invalid"      # spent by the refusal
