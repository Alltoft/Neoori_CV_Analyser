"""The sign-in link, the signup ticket and the address helpers (social
sign-in spec, decisions 4, 15 and 18)."""
import pytest

from app.utils import auth_links


@pytest.mark.parametrize("raw, expected", [
    ("  Marie@Test.FR ", "marie@test.fr"),
    ("marie@test.fr", "marie@test.fr"),
    (None, ""), (42, ""), (["marie@test.fr"], ""),
])
def test_an_address_has_one_stored_form(raw, expected):
    assert auth_links.normalise_email(raw) == expected


@pytest.mark.parametrize("email", ["marie@test.fr", "marie.dupont+cv@sub.example.org"])
def test_a_plain_address_passes_the_shape_check(email):
    assert auth_links.email_shape_ok(email)


@pytest.mark.parametrize("email", [
    "", "marie", "marie@", "@test.fr", "marie@test", "ma rie@test.fr", "marie@@test.fr",
    "marie@test.fr\n", "ma\x00rie@test.fr", "\ud800@test.fr", "a" * 250 + "@test.fr",
    None, 42,
])
def test_anything_else_fails_it(email):
    assert not auth_links.email_shape_ok(email)


def test_the_hash_hides_the_address_and_ignores_its_case(app):
    digest = auth_links.email_hash("Marie@Test.fr")
    assert digest == auth_links.email_hash("marie@test.fr")
    assert len(digest) == 64 and "marie" not in digest


def test_the_hash_is_keyed_on_the_secret(app):
    before = auth_links.email_hash("marie@test.fr")
    app.config["SECRET_KEY"] = "another-key"
    assert auth_links.email_hash("marie@test.fr") != before


def test_a_login_link_round_trips(app):
    token = auth_links.make_login_token("j-1", "marie@test.fr", "/analyse/nouveau")
    result = auth_links.load_login_token(token)
    assert result.error is None
    assert result.payload == {"jti": "j-1", "email": "marie@test.fr", "next": "/analyse/nouveau"}


def test_a_login_link_drops_an_unsafe_destination(app):
    token = auth_links.make_login_token("j-1", "marie@test.fr", "//evil.com")
    assert auth_links.load_login_token(token).payload["next"] is None


def test_a_login_link_expires(app, monkeypatch):
    token = auth_links.make_login_token("j-1", "marie@test.fr")
    monkeypatch.setattr(auth_links, "LOGIN_MAX_AGE", -1)
    assert auth_links.load_login_token(token).error == "link_expired"


def test_a_link_lives_fifteen_minutes_and_a_ticket_thirty():
    assert auth_links.LOGIN_MAX_AGE == 15 * 60
    assert auth_links.SIGNUP_MAX_AGE == 30 * 60


def test_each_purpose_refuses_the_others_tokens(app):
    login = auth_links.make_login_token("j-1", "marie@test.fr")
    ticket = auth_links.make_signup_ticket(method="email", sub=None, email="marie@test.fr")
    assert auth_links.load_signup_ticket(login).error == "link_invalid"
    assert auth_links.load_login_token(ticket).error == "link_invalid"
    assert auth_links.load_verify_token(login).error == "link_invalid"


def test_a_ticket_round_trips(app):
    ticket = auth_links.make_signup_ticket(
        method="google", sub="1234", email="marie@gmail.com",
        prenom_hint="Marie", next_path="/espace",
    )
    assert auth_links.load_signup_ticket(ticket).payload == {
        "method": "google", "sub": "1234", "email": "marie@gmail.com",
        "prenom_hint": "Marie", "next": "/espace",
    }


def test_a_ticket_expires(app, monkeypatch):
    ticket = auth_links.make_signup_ticket(method="email", sub=None, email="marie@test.fr")
    monkeypatch.setattr(auth_links, "SIGNUP_MAX_AGE", -1)
    assert auth_links.load_signup_ticket(ticket).error == "link_expired"
