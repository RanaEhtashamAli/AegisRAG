from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
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

    def authenticate(self, email: str, password: str) -> tuple["User", str]:
        """Verify credentials. Returns (user, access_token) on success."""
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive.")
        token = create_access_token(str(user.id))
        return user, token
