"""Tests for security utilities: password hashing and RS256 JWT round-trips."""

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-pw")
    assert hashed != "s3cret-pw"  # never stored in plaintext
    assert verify_password("s3cret-pw", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip_carries_claims() -> None:
    token = create_access_token(subject="user-1", tenant_id="tenant-1", role="ADVISOR")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["tenant_id"] == "tenant-1"
    assert claims["role"] == "ADVISOR"
    assert "exp" in claims


def test_expired_token_is_rejected() -> None:
    token = create_access_token(
        subject="user-1", tenant_id="tenant-1", role="ADVISOR", expires_minutes=-1
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)
