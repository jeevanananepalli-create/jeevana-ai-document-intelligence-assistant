"""Security primitives: password hashing and JWT helpers.

Phase 1 deliberately ships these as *standalone, tested utilities* — not a login
flow. There is no user table, no `/auth/register`, and no `/auth/login` yet.
That belongs to a later phase. What we establish now is the correct, secure way
to (a) store passwords and (b) mint and read tokens, so the feature work later
just calls these functions.

Why these primitives matter
----------------------------
Password hashing: we NEVER store raw passwords. We store a bcrypt hash. bcrypt
is a deliberately slow, salted hashing function, which makes large-scale
brute-force and rainbow-table attacks impractical. Each hash embeds its own
random salt, so two users with the same password get different hashes.

JWT (JSON Web Token): a signed token the server hands to a client after login.
The client returns it on each request; the server verifies the signature
*without* a database lookup (stateless auth). The signature — not encryption —
is the point: anyone can read a JWT's contents, so we never put secrets in it,
but nobody can forge or tamper with one without the secret key.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt operates on the first 72 bytes of the input and raises on longer input
# in recent versions. We cap explicitly so the behaviour is predictable and the
# limit is documented rather than discovered in production.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt, returning a storable string.

    The returned value includes the algorithm, cost factor, and a random salt,
    so it is fully self-describing and safe to store in the database.
    """
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash.

    Uses bcrypt's constant-time comparison, which avoids leaking information
    through timing differences. Returns False (rather than raising) if the
    stored hash is malformed, so callers can treat it as a failed login.
    """
    try:
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed, short-lived JWT access token.

    Args:
        subject: who the token is about — typically the user id. Stored in the
            standard `sub` claim.
        expires_delta: optional custom lifetime; defaults to the configured
            access-token expiry.
        extra_claims: optional additional claims (e.g. a role). Never put
            sensitive data here — JWT payloads are readable by anyone.

    Returns:
        The encoded JWT as a string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,  # issued-at
        "exp": expire,  # expiry — PyJWT rejects the token automatically after this
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Verify a JWT's signature and expiry, returning its claims.

    Raises:
        jwt.ExpiredSignatureError: the token is past its `exp`.
        jwt.InvalidTokenError: the signature is invalid or the token is malformed.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
