"""« Finaliser votre inscription »: the account a signup ticket was waiting
for (social sign-in spec, decisions 1 and 18–22)."""
import logging
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.profile import CONSENT_VERSION, Profile
from app.models.user import User
from app.routes.auth import password_matches
from app.services import sign_in
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
FORM = {"prenom": "Marie", "tranche_age": "25_34", "consent": True}


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _give_ticket(client, method="google", sub="g-1", email="marie@gmail.com",
                 prenom_hint="Marie", next_path=None):
    client.set_cookie(
        "signup_ticket",
        auth_links.make_signup_ticket(method=method, sub=sub, email=email,
                                      prenom_hint=prenom_hint, next_path=next_path),
        path="/api/auth",
    )


def _signup(client, **form):
    return client.post("/api/auth/signup", json={**FORM, **form})


# ── GET ───────────────────────────────────────────────────────────────────────

def test_the_page_learns_the_address_and_the_prenom_to_prefill(client):
    _give_ticket(client)
    res = client.get("/api/auth/signup")
    assert res.status_code == 200
    assert res.get_json() == {"email": "marie@gmail.com", "prenom": "Marie", "method": "google"}


def test_without_a_ticket_there_is_nothing_to_finalise(client):
    res = client.get("/api/auth/signup")
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"


def test_an_expired_ticket_says_so(client, monkeypatch):
    _give_ticket(client)
    monkeypatch.setattr(auth_links, "SIGNUP_MAX_AGE", -1)
    assert client.get("/api/auth/signup").get_json()["code"] == "link_expired"


# ── POST ──────────────────────────────────────────────────────────────────────

def test_finalising_creates_the_account_its_identity_and_its_consent_at_once(client):
    _give_ticket(client, next_path="/analyse/nouveau")
    res = _signup(client)
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert "access_token_cookie" in _cookies(res)
    user = User.query.one()
    assert user.email == "marie@gmail.com" and user.email_verified_at is not None
    assert AuthIdentity.query.one().subject == "g-1"
    profile = Profile.query.one()
    assert (profile.prenom, profile.tranche_age) == ("Marie", "25_34")
    assert profile.consent_at is not None and profile.consent_version == CONSENT_VERSION


def test_finalising_spends_the_ticket(client):
    _give_ticket(client)
    _signup(client)
    assert client.get_cookie("signup_ticket", path="/api/auth") is None


def test_an_email_ticket_makes_an_account_with_no_identity(client):
    _give_ticket(client, method="email", sub=None, email="marie@test.fr", prenom_hint="")
    assert _signup(client).status_code == 200
    assert User.query.one().email == "marie@test.fr"
    assert AuthIdentity.query.count() == 0


def test_the_new_account_has_no_password_until_one_is_set(client):
    _give_ticket(client)
    _signup(client)
    assert not password_matches(User.query.one(), "motdepasse1")
    login = client.post("/api/auth/login",
                        json={"email": "marie@gmail.com", "password": "n'importe"})
    assert login.status_code == 401


def test_no_mail_leaves_when_the_account_is_created(client, app):
    app.config["RESEND_API_KEY"] = "re_test"
    _give_ticket(client)
    with patch(SEND) as mock_send:
        _signup(client)
    mock_send.assert_not_called()


@pytest.mark.parametrize("form, message", [
    ({"prenom": ""}, "Prénom requis."),
    ({"prenom": "   "}, "Prénom requis."),
    ({"tranche_age": ""}, "Tranche d'âge requise."),
    ({"consent": False}, "Le consentement est requis."),
    ({"consent": "true"}, "Le consentement est requis."),
    ({"tranche_age": "moins_25"}, "Valeur invalide pour tranche_age."),
    ({"tranche_age": "14_99"}, "Valeur invalide pour tranche_age."),
])
def test_a_refused_form_creates_nothing_and_keeps_the_ticket(client, form, message):
    _give_ticket(client)
    res = _signup(client, **form)
    assert res.status_code == 400 and res.get_json()["error"] == message
    assert User.query.count() == 0
    assert client.get_cookie("signup_ticket", path="/api/auth") is not None


def test_without_a_ticket_nothing_is_created(client):
    res = _signup(client)
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"
    assert User.query.count() == 0


def test_an_address_claimed_meanwhile_is_entered_not_duplicated(client, make_user):
    existing = make_user(email="marie@gmail.com")
    _give_ticket(client)
    res = _signup(client, prenom="Autre")
    assert res.status_code == 200
    assert res.get_json()["user"]["id"] == existing.id
    assert User.query.count() == 1
    assert Profile.query.count() == 0          # the form never overwrites an account
    assert password_matches(db.session.get(User, existing.id), "motdepasse1")


def test_a_second_submit_enters_the_first_one_s_account(client):
    # Review Focus 3: the double click left before the first answer cleared the cookie.
    _give_ticket(client)
    first = _signup(client)
    _give_ticket(client)
    second = _signup(client)
    assert second.status_code == 200
    assert second.get_json()["user"]["id"] == first.get_json()["user"]["id"]
    assert User.query.count() == 1
    assert AuthIdentity.query.count() == 1 and Profile.query.count() == 1


def test_a_submit_that_loses_the_race_enters_the_winner_s_account(client, monkeypatch):
    # Review Focus 3: both submits looked before either committed.
    _give_ticket(client)
    winner = _signup(client).get_json()["user"]["id"]
    _give_ticket(client)
    real_existing, real_in_use = sign_in.existing_account, sign_in.address_in_use
    looks = []

    def blind_at_first(*args):
        looks.append(args)
        return None if len(looks) == 1 else real_existing(*args)

    in_use_looks = []

    def free_at_first(email):
        in_use_looks.append(email)
        return False if len(in_use_looks) == 1 else real_in_use(email)

    monkeypatch.setattr(sign_in, "existing_account", blind_at_first)
    monkeypatch.setattr(sign_in, "address_in_use", free_at_first)
    res = _signup(client, prenom="Perdant")
    assert res.status_code == 200
    assert res.get_json()["user"]["id"] == winner
    assert User.query.count() == 1
    assert Profile.query.one().prenom == "Marie"


def test_a_submit_whose_twin_committed_between_the_two_looks_enters_it(client, monkeypatch):
    # The winner commits after this request's first look but before its
    # address check: the second look must find and enter it, not refuse.
    _give_ticket(client)
    winner = _signup(client).get_json()["user"]["id"]
    _give_ticket(client)
    real = sign_in.existing_account
    looks = []

    def blind_at_first(*args):
        looks.append(args)
        return None if len(looks) == 1 else real(*args)

    monkeypatch.setattr(sign_in, "existing_account", blind_at_first)
    res = _signup(client)
    assert res.status_code == 200
    assert res.get_json()["user"]["id"] == winner
    assert User.query.count() == 1


def test_finalising_onto_an_address_held_by_a_lookalike_is_refused(client, make_user, monkeypatch):
    lookalike = make_user(email="marie@gmaïl.com")
    _give_ticket(client)                     # proves marie@gmail.com
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    res = _signup(client)
    assert res.status_code == 409 and res.get_json()["code"] == "address_unavailable"
    assert User.query.count() == 1           # only the lookalike
    assert AuthIdentity.query.count() == 0 and Profile.query.count() == 0
    assert client.get_cookie("signup_ticket", path="/api/auth") is not None


def test_a_collision_after_the_users_row_leaves_nothing_behind(client, make_user, monkeypatch):
    # Pins the single commit (no users row committed before its identity and consent) and the fallback 409.
    other = make_user(email="autre@test.fr")
    db.session.add(AuthIdentity(user_id=other.id, provider="google", subject="g-1"))
    db.session.commit()
    _give_ticket(client)
    monkeypatch.setattr(sign_in, "existing_account", lambda *a: None)
    monkeypatch.setattr(sign_in, "address_in_use", lambda email: False)
    res = _signup(client)
    assert res.status_code == 409 and res.get_json()["code"] == "address_unavailable"
    assert User.query.filter_by(email="marie@gmail.com").count() == 0
    assert Profile.query.count() == 0
    assert client.get_cookie("signup_ticket", path="/api/auth") is not None


def test_a_fallback_after_an_integrity_error_is_logged(client, make_user, monkeypatch, caplog):
    # The unique constraints settling a race should be rare: when they do,
    # the log says so. The message names no address.
    other = make_user(email="autre@test.fr")
    db.session.add(AuthIdentity(user_id=other.id, provider="google", subject="g-1"))
    db.session.commit()
    _give_ticket(client)
    monkeypatch.setattr(sign_in, "existing_account", lambda *a: None)
    monkeypatch.setattr(sign_in, "address_in_use", lambda email: False)
    with caplog.at_level(logging.WARNING):
        assert _signup(client).status_code == 409
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [r.getMessage() for r in warnings] == ["POST /signup fell back after an IntegrityError."]
    assert warnings[0].exc_info is not None


def test_a_prenom_longer_than_the_column_is_refused_not_a_500(client):
    # Review Focus 4: SQLite stores it; MySQL raises "Data too long".
    _give_ticket(client)
    res = _signup(client, prenom="M" * 121)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Le prénom est trop long : 120 caractères maximum."
    assert User.query.count() == 0


def test_register_refuses_it_too(client):
    # Review Focus 4: the shared seed helper guards the password signup as well.
    res = client.post("/api/auth/register", json={
        "email": "long@test.fr", "password": "motdepasse1",
        "prenom": "M" * 121, "tranche_age": "25_34", "consent": True,
    })
    assert res.status_code == 400
    assert User.query.count() == 0


def test_a_prenom_that_cannot_be_stored_is_refused(client):
    _give_ticket(client)
    res = _signup(client, prenom="Ma\ud800rie")
    assert res.status_code == 400
    assert User.query.count() == 0
