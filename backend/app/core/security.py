from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import jwt

from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises jose.JWTError if invalid."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
