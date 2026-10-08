"""Signed, expiring tokens for everything that proves an inbox: the links that
confirm an address, reset a password or sign in, and the signup ticket a
proven address carries to « Finaliser votre inscription ».

Stateless on purpose (email verification spec, decision 3): the link carries
its own proof, signed with SECRET_KEY, so there is no token table to store,
expire or clean up. The sign-in link is the one exception: its single use
lives in the login_links table (social sign-in spec, decision 17). One salt
per purpose, so a link minted for one job is refused by the other. Rotating
SECRET_KEY kills every link in flight — the person asks for a new one.
"""
import hashlib
import hmac
import re
from dataclasses import dataclass

from flask import current_app
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

VERIFY_SALT = "email-verify"
RESET_SALT = "password-reset"
VERIFY_MAX_AGE = 48 * 3600   # seconds
RESET_MAX_AGE = 3600
NEXT_MAX_LENGTH = 512
LOGIN_SALT = "email-login"
SIGNUP_SALT = "signup-ticket"
LOGIN_MAX_AGE = 15 * 60      # social sign-in spec, decision 15
SIGNUP_MAX_AGE = 30 * 60     # decision 18
EMAIL_MAX_LENGTH = 255       # users.email
# One @, a dot after it, no whitespace or control character anywhere.
_EMAIL_SHAPE = re.compile(
    r"[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+\.[^@\s\x00-\x1f\x7f]+"
)
# Dot segments as a URL parser reads them, percent-encoded forms included:
# "/..//evil.com" and "/%2e%2e//evil.com" both resolve to the path
# "//evil.com", which a router then takes for another host.
_DOT_SEGMENTS = frozenset({".", "..", "%2e", ".%2e", "%2e.", "%2e%2e"})


@dataclass(frozen=True)
class LinkResult:
    payload: dict | None
    error: str | None   # None, "link_expired" or "link_invalid"


def password_fingerprint(password_hash: str) -> str:
    """16 hex chars of sha256(password_hash). It changes whenever the password
    does, which makes a reset link single-use and lets /refresh end every
    session minted under an old password."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def safe_next(value) -> str | None:
    """A local path (query string allowed), or None. Anything else would make
    the link an open redirect signed by neoori.

    Judged as given, never decoded or normalised: refusing what could resolve
    elsewhere is safer than rewriting it into something that cannot. Same
    rules as the frontend's safeRedirect (lib/safe-redirect.ts)."""
    if not isinstance(value, str):
        return None
    if (
        not value.startswith("/")
        or value.startswith("//")
        or value.startswith("/\\")
        or len(value) > NEXT_MAX_LENGTH
        # Every C0 control and DEL: a browser drops tab and newline before
        # parsing, so "/<TAB>/evil.com" would start like a path and resolve
        # as "//evil.com".
        or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value)
        # A lone surrogate cannot be encoded as UTF-8, and the token minters
        # would raise UnicodeEncodeError when JSON-serialising the path.
        or any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)
        or _has_dot_segment(value)
    ):
        return None
    return value


def _has_dot_segment(value: str) -> bool:
    """A "." or ".." segment in the path part, before any ? or #. A backslash
    separates segments too: browsers read it as a slash."""
    path = re.split(r"[?#]", value, maxsplit=1)[0]
    return any(seg.lower() in _DOT_SEGMENTS for seg in re.split(r"[/\\]", path))


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _load(salt: str, token, max_age: int) -> LinkResult:
    if not isinstance(token, str) or not token:
        return LinkResult(None, "link_invalid")
    try:
        data = _serializer(salt).loads(token, max_age=max_age)
    except SignatureExpired:          # subclass of BadData: must come first
        return LinkResult(None, "link_expired")
    except (BadData, UnicodeError):   # a lone surrogate cannot even be encoded
        return LinkResult(None, "link_invalid")
    if not isinstance(data, dict):
        return LinkResult(None, "link_invalid")
    return LinkResult(data, None)


def make_verify_token(user, next_path=None) -> str:
    return _serializer(VERIFY_SALT).dumps(
        {"uid": user.id, "email": user.email, "next": safe_next(next_path)}
    )


def load_verify_token(token) -> LinkResult:
    return _load(VERIFY_SALT, token, VERIFY_MAX_AGE)


def make_reset_token(user) -> str:
    return _serializer(RESET_SALT).dumps(
        {"uid": user.id, "pwv": password_fingerprint(user.password_hash)}
    )


def load_reset_token(token) -> LinkResult:
    return _load(RESET_SALT, token, RESET_MAX_AGE)


def normalise_email(raw) -> str:
    """The one form an address is stored and looked up under — the one
    register stores: stripped, lowercased. Anything but a string is ""."""
    return raw.strip().lower() if isinstance(raw, str) else ""


def email_shape_ok(email) -> bool:
    """A light check before an address is mailed or stored: ASCII addresses only,
    the right shape, and fits users.email. MySQL's utf8mb4_unicode_ci collation
    compares accented letters equal to their base letters, so a non-ASCII lookalike
    (marie@gmaïl.com for marie@gmail.com) could enter another person's account."""
    if not isinstance(email, str) or not 0 < len(email) <= EMAIL_MAX_LENGTH:
        return False
    if not email.isascii():
        return False
    return _EMAIL_SHAPE.fullmatch(email) is not None


def email_hash(email: str) -> str:
    """What login_links keeps instead of the address (social sign-in spec,
    decision 4): an HMAC of the normalised address keyed on SECRET_KEY, so a
    table dump does not tell which known addresses asked for a link. Call it
    on a shape-checked address."""
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, normalise_email(email).encode("utf-8"), hashlib.sha256).hexdigest()


def make_login_token(jti: str, email: str, next_path=None) -> str:
    return _serializer(LOGIN_SALT).dumps(
        {"jti": jti, "email": email, "next": safe_next(next_path)}
    )


def load_login_token(token) -> LinkResult:
    return _load(LOGIN_SALT, token, LOGIN_MAX_AGE)


def make_signup_ticket(*, method: str, sub, email: str, prenom_hint: str = "",
                       next_path=None) -> str:
    return _serializer(SIGNUP_SALT).dumps({
        "method": method, "sub": sub, "email": email,
        "prenom_hint": prenom_hint, "next": safe_next(next_path),
    })


def load_signup_ticket(token) -> LinkResult:
    return _load(SIGNUP_SALT, token, SIGNUP_MAX_AGE)
