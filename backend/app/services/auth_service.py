from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import UserRegister


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, data: UserRegister) -> User:
        if self.db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered.")
        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role="viewer",  # new registrations start as viewer until assigned to a tenant
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _issue_refresh_token(self, user_id) -> str:
        raw_token = generate_refresh_token()
        record = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(record)
        self.db.commit()
        return raw_token

    def authenticate(self, email: str, password: str) -> tuple[User, str, str]:
        """Verify credentials. Returns (user, access_token, refresh_token) on success."""
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive.")
        access_token = create_access_token(str(user.id))
        refresh_token = self._issue_refresh_token(user.id)
        return user, access_token, refresh_token

    def refresh_access_token(self, raw_refresh_token: str) -> tuple[User, str, str]:
        """Validate + rotate a refresh token. Returns (user, new_access_token, new_refresh_token)."""
        token_hash = hash_refresh_token(raw_refresh_token)
        record = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        now = datetime.now(UTC)
        if (
            not record
            or record.revoked_at is not None
            or record.expires_at < now
        ):
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

        user = self.db.query(User).filter(User.id == record.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

        record.revoked_at = now  # rotation: this token is single-use
        self.db.commit()

        access_token = create_access_token(str(user.id))
        new_refresh_token = self._issue_refresh_token(user.id)
        return user, access_token, new_refresh_token

    def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        """Best-effort logout: revoke if the token exists, no-op (not an error) otherwise."""
        token_hash = hash_refresh_token(raw_refresh_token)
        record = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(UTC)
            self.db.commit()
