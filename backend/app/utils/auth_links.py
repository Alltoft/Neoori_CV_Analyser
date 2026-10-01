"""Signed, expiring links for the two mails that prove an inbox: confirming an
address, and resetting a password.

Stateless on purpose (email verification spec, decision 3): the link carries
its own proof, signed with SECRET_KEY, so there is no token table to store,
expire or clean up. One salt per purpose, so a link minted for one job is
refused by the other. Rotating SECRET_KEY kills every link in flight — the
person asks for a new one.
"""
import hashlib
from dataclasses import dataclass

from flask import current_app
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

VERIFY_SALT = "email-verify"
RESET_SALT = "password-reset"
VERIFY_MAX_AGE = 48 * 3600   # seconds
RESET_MAX_AGE = 3600
NEXT_MAX_LENGTH = 512


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
    the link an open redirect signed by neoori."""
    if not isinstance(value, str):
        return None
    if (
        not value.startswith("/")
        or value.startswith("//")
        or value.startswith("/\\")
        or len(value) > NEXT_MAX_LENGTH
        or any(ch in value for ch in "\r\n\t")
    ):
        return None
    return value


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
