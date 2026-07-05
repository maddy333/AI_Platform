"""API key generation and verification.

Keys are formatted as ``<prefix>_<hex>``.  Only the SHA-256 hash of the secret
portion is stored in the database; the plaintext is returned once at creation
and never persisted.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiplatform.auth.config import AuthSettings

_SEPARATOR = "_"


@dataclass(frozen=True)
class RawAPIKey:
    """Plaintext key returned to the caller at creation time."""

    plaintext: str
    prefix: str
    secret_hash: str


def generate_api_key(settings: AuthSettings) -> RawAPIKey:
    """Generate a new API key.

    Returns a ``RawAPIKey`` whose ``plaintext`` must be shown to the user
    exactly once.  Store only ``prefix`` and ``secret_hash`` in the database.
    """
    secret_bytes = secrets.token_bytes(settings.api_key_bytes)
    secret_hex = secret_bytes.hex()
    plaintext = f"{settings.api_key_prefix}{_SEPARATOR}{secret_hex}"
    prefix = plaintext[:12]
    secret_hash = _hash_secret(secret_hex)
    return RawAPIKey(plaintext=plaintext, prefix=prefix, secret_hash=secret_hash)


def hash_api_key(plaintext: str) -> tuple[str, str]:
    """Return ``(prefix, secret_hash)`` for an existing plaintext key.

    Used during verification: the caller provides the full key, we split it and
    compare the hash against the stored value.
    """
    if _SEPARATOR not in plaintext:
        msg = "Malformed API key: missing separator."
        raise ValueError(msg)
    prefix = plaintext[:12]
    secret_hex = plaintext.split(_SEPARATOR, 1)[1]
    return prefix, _hash_secret(secret_hex)


def verify_api_key(plaintext: str, stored_hash: str) -> bool:
    """Return ``True`` if *plaintext* matches *stored_hash* using constant-time comparison."""
    try:
        _, computed_hash = hash_api_key(plaintext)
    except ValueError:
        return False
    return secrets.compare_digest(computed_hash, stored_hash)


def _hash_secret(secret_hex: str) -> str:
    return hashlib.sha256(secret_hex.encode()).hexdigest()
