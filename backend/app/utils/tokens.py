import secrets
import string


def generate_share_token(length: int = 32) -> str:
    """URL-safe random token for counselor share links."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
