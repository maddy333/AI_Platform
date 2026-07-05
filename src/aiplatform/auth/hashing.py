"""Argon2id password hashing.

Uses argon2-cffi with OWASP-recommended parameters.  The hasher is a module-
level singleton so the expensive parameter setup happens once at import time.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from aiplatform.auth.domain.errors import InvalidCredentialsError

# OWASP recommended Argon2id parameters (2024):
# time_cost=2, memory_cost=19456 (19 MiB), parallelism=1
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Return an Argon2id hash of *plain*."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> None:
    """Verify *plain* against *hashed*.

    Raises ``InvalidCredentialsError`` on mismatch or hash corruption.
    """
    try:
        _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError) as exc:
        raise InvalidCredentialsError("Invalid password.") from exc


def needs_rehash(hashed: str) -> bool:
    """Return ``True`` if the stored hash uses outdated parameters."""
    return _hasher.check_needs_rehash(hashed)
