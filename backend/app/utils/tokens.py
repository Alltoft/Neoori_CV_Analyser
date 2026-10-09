import hashlib
import secrets
import string


def generate_share_token(length: int = 32) -> str:
    """URL-safe random token for counselor share links."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def new_access_token() -> str:
    """The key to a no-login report or a held draft (four-doors spec,
    decisions 30, 34): 32 random bytes, URL-safe. Only hash_token() of it is
    ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
