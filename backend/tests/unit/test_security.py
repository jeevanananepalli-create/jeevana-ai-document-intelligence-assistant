"""Tests for the password-hashing and JWT utilities.

These are pure-function tests: no database, no HTTP. They document the security
guarantees the rest of the app will rely on.
"""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plaintext() -> None:
    """A hash must never equal the original password."""
    assert hash_password("s3cret-pass") != "s3cret-pass"


def test_hash_is_salted_so_two_hashes_differ() -> None:
    """The same password hashed twice yields different hashes (random salt)."""
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_accepts_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_rejects_malformed_hash_without_raising() -> None:
    """A garbage stored hash is treated as a failed match, not an exception."""
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_access_token_round_trips_subject() -> None:
    """A freshly minted token decodes back to the same subject."""
    token = create_access_token(subject="user-123")
    claims = decode_token(token)
    assert claims["sub"] == "user-123"


def test_access_token_includes_extra_claims() -> None:
    token = create_access_token(subject="user-123", extra_claims={"role": "admin"})
    assert decode_token(token)["role"] == "admin"


def test_expired_token_is_rejected() -> None:
    """A token whose expiry is in the past fails verification."""
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)
