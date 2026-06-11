import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_user
from app.core.enums import UserRole
from app.core.permissions import require_tenant_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.invitation import AcceptInviteRequest, InvitationResponse, InviteUserRequest
from app.schemas.user_mgmt import TenantUserResponse, UserRoleUpdate
from app.services.audit_service import AuditService
from app.services.invitation_service import InvitationService

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Invitation endpoints (no tenant required for accept-invite)
# ---------------------------------------------------------------------------


@router.post("/invite", response_model=InvitationResponse, status_code=201)
def invite_user(
    body: InviteUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_tenant_admin()),
) -> InvitationResponse:
    invitation, raw_token = InvitationService(db).invite_user(
        email=body.email,
        role=body.role,
        inviter=admin,
        full_name=body.full_name,
    )
    AuditService(db).log(
        event_type="user.invited",
        user_id=admin.id,
        tenant_id=admin.tenant_id,
        entity_type="invitation",
        entity_id=str(invitation.id),
        metadata={"email": body.email, "role": body.role},
    )
    # Return the raw token in the response — this is the only time it is visible
    response = InvitationResponse.model_validate(invitation)
    response.invite_token = raw_token
    return response


@router.post("/accept-invite", response_model=UserResponse)
def accept_invite(
    body: AcceptInviteRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = InvitationService(db).accept_invite(
        raw_token=body.token,
        password=body.password,
        full_name=body.full_name,
    )
    AuditService(db).log(
        event_type="user.invite_accepted",
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity_type="user",
        entity_id=str(user.id),
        metadata={"email": user.email, "role": user.role},
    )
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# User management (tenant-scoped)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TenantUserResponse])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> list[TenantUserResponse]:
    """tenant_admin and compliance_officer may list users."""
    if UserRole(user.role) not in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}:
        raise HTTPException(
            status_code=403, detail="You do not have permission to list users."
        )
    users = (
        db.query(User)
        .filter(User.tenant_id == user.tenant_id, User.is_active == True)  # noqa: E712
        .order_by(User.created_at.asc())
        .all()
    )
    return [TenantUserResponse.model_validate(u) for u in users]


@router.patch("/{user_id}/role", response_model=TenantUserResponse)
def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_tenant_admin()),
) -> TenantUserResponse:
    target = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == admin.tenant_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Prevent self-demotion if the only admin
    if str(target.id) == str(admin.id) and body.role != UserRole.TENANT_ADMIN.value:
        other_admins = (
            db.query(User)
            .filter(
                User.tenant_id == admin.tenant_id,
                User.role == UserRole.TENANT_ADMIN.value,
                User.is_active == True,  # noqa: E712
                User.id != admin.id,
            )
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote yourself — you are the only tenant admin.",
            )

    old_role = target.role
    target.role = body.role
    db.commit()
    db.refresh(target)

    AuditService(db).log(
        event_type="user.role_updated",
        user_id=admin.id,
        tenant_id=admin.tenant_id,
        entity_type="user",
        entity_id=str(target.id),
        metadata={
            "target_email": target.email,
            "old_role": old_role,
            "new_role": body.role,
        },
    )
    return TenantUserResponse.model_validate(target)


@router.delete("/{user_id}", status_code=204)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_tenant_admin()),
) -> None:
    target = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == admin.tenant_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if str(target.id) == str(admin.id):
        raise HTTPException(status_code=409, detail="Cannot deactivate yourself.")

    target.is_active = False
    db.commit()

    AuditService(db).log(
        event_type="user.deactivated",
        user_id=admin.id,
        tenant_id=admin.tenant_id,
        entity_type="user",
        entity_id=str(target.id),
        metadata={"target_email": target.email},
    )
