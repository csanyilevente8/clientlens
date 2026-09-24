"""Security utilities: password hashing and JWT (RS256) creation/verification.

Java/Spring analog:
- hash_password/verify_password ≈ PasswordEncoder (BCrypt).
- create_access_token/decode_access_token ≈ a JwtEncoder/JwtDecoder.

These are pure, side-effect-light functions so they are easy to unit-test in isolation
(no DB, no HTTP). The FastAPI wiring (login endpoint, current-user dependency) lives
elsewhere and uses these.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt hash of the given plaintext password.

    We use the `bcrypt` library directly rather than passlib: passlib is unmaintained and
    incompatible with bcrypt >= 4.1 (see ADR-009 / commit notes). bcrypt handles salting.
    """
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plaintext matches the stored hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(
    *,
    subject: str,
    tenant_id: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed RS256 access token.

    Claims:
    - sub:       the user id (subject)
    - tenant_id: the user's tenant (resolved server-side, embedded here so downstream
                 services can trust it without a DB lookup)
    - role:      the user's role (embedded per ADR: roles change rarely)
    - exp/iat:   expiry / issued-at
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a token, returning its claims.

    Raises jwt.PyJWTError (e.g. ExpiredSignatureError, InvalidTokenError) on any failure;
    callers translate that into a 401.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_public_key, algorithms=[settings.jwt_algorithm])
