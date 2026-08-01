from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.security_alert_service import SecurityAlertService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)) -> User:
    return AuthService(db).register(data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    data: UserLogin, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent")
    try:
        user, token = AuthService(db).authenticate(data.email, data.password)
        AuditService(db).log(
            event_type="auth.login_success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            metadata={"email": data.email},
            ip_address=ip,
            user_agent=ua,
        )
        return TokenResponse(access_token=token)
    except Exception:
        AuditService(db).log(
            event_type="auth.login_failed",
            metadata={"email": data.email},
            ip_address=ip,
        )
        try:
            SecurityAlertService(db).check_failed_logins(data.email, ip)
        except Exception:
            pass  # never block login flow because of alert side-effect
        raise


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
