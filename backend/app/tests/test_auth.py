import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_round_trip() -> None:
    password = "supersecretpassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_rejected() -> None:
    hashed = hash_password("correct_password")
    assert not verify_password("wrong_password", hashed)


def test_jwt_round_trip() -> None:
    token = create_access_token("user-abc-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-abc-123"


def test_jwt_invalid_token_raises() -> None:
    with pytest.raises(JWTError):
        decode_access_token("this.is.not.valid")


def test_jwt_tampered_token_raises() -> None:
    token = create_access_token("user-xyz")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(JWTError):
        decode_access_token(tampered)
