"""Field-level encryption for the sensitive half of a profile.

CDC v1.2 / PM ruling: the base profile is erasable under consent, but bloc 5
(work conditions) and the OETH flag are "stockés à part, chiffrés, hors des
logs". They live in their own table with ciphertext columns and are decrypted
in-process only to compose the AI prompt — never returned by the API, never
written to a log, never rendered into a PDF.

Fernet (AES-128-CBC + HMAC-SHA256, versioned token format) comes from
`cryptography`, which is already a dependency via PyMySQL. MultiFernet gives
key rotation: the first key encrypts, all keys are tried on decrypt, so you
can prepend a new key and re-save rows at your leisure.

Generate a key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Set:             FIELD_ENCRYPTION_KEYS=<newest>,<previous>
"""
import base64
import json
import logging
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

log = logging.getLogger(__name__)

_CACHE: dict = {}


class DecryptionError(RuntimeError):
    """Ciphertext could not be read with any configured key."""


def _derive_from_secret(secret: str) -> bytes:
    """Deterministic fallback key, so a missing env var doesn't lose data.

    Rotating SECRET_KEY makes rows encrypted this way unreadable — which is
    exactly why production should set FIELD_ENCRYPTION_KEYS explicitly.
    """
    raw = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"neoori-field-encryption-v1",
        info=b"sensitive-profile",
    ).derive(secret.encode())
    return base64.urlsafe_b64encode(raw)


def _fernet() -> MultiFernet:
    configured = os.getenv("FIELD_ENCRYPTION_KEYS", "").strip()
    cache_key = configured or "__derived__"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if configured:
        keys = [Fernet(k.strip().encode()) for k in configured.split(",") if k.strip()]
    else:
        secret = os.getenv("SECRET_KEY") or "dev-secret-change-in-prod"
        if os.getenv("FLASK_ENV") == "production":
            log.warning(
                "FIELD_ENCRYPTION_KEYS is unset — deriving the field key from "
                "SECRET_KEY. Rotating SECRET_KEY will make encrypted profile "
                "data unreadable. Set FIELD_ENCRYPTION_KEYS."
            )
        keys = [Fernet(_derive_from_secret(secret))]

    if not keys:
        raise RuntimeError("FIELD_ENCRYPTION_KEYS is set but contains no usable key.")

    mf = MultiFernet(keys)
    _CACHE[cache_key] = mf
    return mf


def reset_cache() -> None:
    """Drop the cached key set — for tests that swap the env var."""
    _CACHE.clear()


def encrypt(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        # Never echo the ciphertext or the key set into the log.
        raise DecryptionError(
            "Sensitive profile field could not be decrypted with any configured key."
        ) from exc


def encrypt_json(value) -> str | None:
    """Encrypt a JSON-serialisable value. sort_keys so equal values encrypt
    from identical plaintext (Fernet output still differs — it carries an IV)."""
    if value is None:
        return None
    return encrypt(json.dumps(value, sort_keys=True, ensure_ascii=False))


def decrypt_json(token: str | None):
    raw = decrypt(token)
    return None if raw is None else json.loads(raw)
