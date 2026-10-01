"""Signed, expiring links for the two mails that prove an inbox: confirming an
address, and resetting a password.

Stateless on purpose (email verification spec, decision 3): the link carries
its own proof, signed with SECRET_KEY, so there is no token table to store,
expire or clean up. One salt per purpose, so a link minted for one job is
refused by the other. Rotating SECRET_KEY kills every link in flight — the
person asks for a new one.
"""
import hashlib
import re
from dataclasses import dataclass

from flask import current_app
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

VERIFY_SALT = "email-verify"
RESET_SALT = "password-reset"
VERIFY_MAX_AGE = 48 * 3600   # seconds
RESET_MAX_AGE = 3600
NEXT_MAX_LENGTH = 512
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
