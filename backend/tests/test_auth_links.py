"""Signed links for the two account mails (email verification spec,
decisions 3–7)."""
import pytest

from app.models.user import User
from app.utils import auth_links


def _user(**overrides):
    fields = dict(id="u-1", email="marie@test.fr", password_hash="$2b$04$hash-one")
    fields.update(overrides)
    return User(**fields)


def _tamper_payload(token: str) -> str:
    """Flip a character in the payload (before the first "."), ensuring real
    signature bits change. Deterministic: 'A'→'B', anything else→'A'."""
    dot_idx = token.index(".")
    mid = dot_idx // 2
    ch = token[mid]
    new_ch = "B" if ch != "B" else "A"
    return token[:mid] + new_ch + token[mid+1:]


def test_a_verification_link_round_trips(app):
    token = auth_links.make_verify_token(_user(), "/analyse/nouveau")
    result = auth_links.load_verify_token(token)
    assert result.error is None
    assert result.payload == {"uid": "u-1", "email": "marie@test.fr", "next": "/analyse/nouveau"}


@pytest.mark.parametrize("bad", [
    "//evil.com", "/\\evil.com", "https://evil.com", "evil.com", "",
    "/ok\r\nSet-Cookie: x=1", "/" + "a" * 600, None, 42, ["/espace"],
    "/a\ud800",
])
def test_next_refuses_anything_but_a_local_path(bad):
    assert auth_links.safe_next(bad) is None


# Dot segments resolve before a router sees the path: each of these becomes
# "//evil.com", another host. Percent-encoded dots count, as they do for the
# URL parser, and so does a backslash as a separator.
@pytest.mark.parametrize("bad", [
    "/..//evil.com", "/.//evil.com", "/a/..//evil.com", "/./x", "/a/../b", "/..",
    "/%2e%2e//evil.com", "/%2E.//evil.com", "/.%2e//evil.com", "/%2e//evil.com",
    "/a\\..\\/evil.com", "/a/..?x=1", "/a/.#top",
])
def test_next_refuses_a_dot_segment(bad):
    assert auth_links.safe_next(bad) is None


@pytest.mark.parametrize("ch", [chr(c) for c in (*range(0x20), 0x7F)])
def test_next_refuses_every_control_character(ch):
    assert auth_links.safe_next(f"/analyse{ch}nouveau") is None


def test_next_keeps_a_local_path_and_its_query():
    # Review Focus 4: the query string of a gated page must survive the trip.
    assert auth_links.safe_next("/analyse/nouveau?draft=abc") == "/analyse/nouveau?draft=abc"


@pytest.mark.parametrize("ok", [
    "/analyse/nouveau?redirect=%2F%2Fevil.com",   # verbatim, never decoded
    "/analyse?next=/..//x",                        # dots after ? are query
    "/espace#/../x",                               # ... and after # fragment
    "/v1.2/rapport", "/a/.well-known", "/a/...", "/a..b/c.",
])
def test_next_keeps_dots_that_are_not_a_segment(ok):
    assert auth_links.safe_next(ok) == ok


def test_an_unsafe_next_is_dropped_from_the_link(app):
    token = auth_links.make_verify_token(_user(), "//evil.com")
    assert auth_links.load_verify_token(token).payload["next"] is None


def test_a_verification_link_is_not_a_reset_link_and_back(app):
    user = _user()
    assert auth_links.load_reset_token(auth_links.make_verify_token(user)).error == "link_invalid"
    assert auth_links.load_verify_token(auth_links.make_reset_token(user)).error == "link_invalid"


def test_a_tampered_link_is_invalid(app):
    token = auth_links.make_verify_token(_user())
    assert auth_links.load_verify_token(_tamper_payload(token)).error == "link_invalid"


@pytest.mark.parametrize("junk", [None, 42, "", "not-a-token", "a.b.c", "\ud800"])
def test_junk_is_invalid_never_an_exception(app, junk):
    assert auth_links.load_verify_token(junk).error == "link_invalid"


def test_an_old_verification_link_is_expired(app, monkeypatch):
    token = auth_links.make_verify_token(_user())
    monkeypatch.setattr(auth_links, "VERIFY_MAX_AGE", -1)
    assert auth_links.load_verify_token(token).error == "link_expired"


def test_a_reset_link_expires_on_its_own_clock(app, monkeypatch):
    token = auth_links.make_reset_token(_user())
    monkeypatch.setattr(auth_links, "RESET_MAX_AGE", -1)
    assert auth_links.load_reset_token(token).error == "link_expired"


def test_a_reset_link_carries_the_password_fingerprint(app):
    user = _user()
    payload = auth_links.load_reset_token(auth_links.make_reset_token(user)).payload
    assert payload == {"uid": "u-1", "pwv": auth_links.password_fingerprint(user.password_hash)}


def test_the_fingerprint_moves_with_the_password():
    one = auth_links.password_fingerprint("$2b$04$hash-one")
    assert len(one) == 16
    int(one, 16)   # hex, or this raises
    assert one != auth_links.password_fingerprint("$2b$04$hash-two")


def test_a_new_secret_key_kills_old_links(app):
    token = auth_links.make_verify_token(_user())
    app.config["SECRET_KEY"] = "rotated"
    assert auth_links.load_verify_token(token).error == "link_invalid"
