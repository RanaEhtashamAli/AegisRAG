import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import InvitationStatus, UserRole
from app.core.security import hash_password
from app.models.invitation import TenantInvitation
from app.models.user import User

_INVITE_EXPIRY_HOURS = 72


class InvitationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def invite_user(
        self,
        email: str,
        role: str,
        inviter: User,
        full_name: str | None = None,
    ) -> tuple[TenantInvitation, str]:
        """Create an invitation. Returns (invitation, raw_token)."""
        if UserRole(role) == UserRole.TENANT_ADMIN:
            # Prevent creating a second tenant_admin via invite — can be changed by role update
            existing_admin = (
                self.db.query(User)
                .filter(
                    User.tenant_id == inviter.tenant_id,
                    User.role == UserRole.TENANT_ADMIN.value,
                    User.is_active == True,  # noqa: E712
                )
                .first()
            )
            if existing_admin:
                raise HTTPException(
                    status_code=409,
                    detail="A tenant admin already exists. Invite the user with a different role then promote them.",
                )

        # Check for existing pending invite for this email in this tenant
        existing_invite = (
            self.db.query(TenantInvitation)
            .filter(
                TenantInvitation.tenant_id == inviter.tenant_id,
                TenantInvitation.email == email,
                TenantInvitation.status == InvitationStatus.PENDING.value,
            )
            .first()
        )
        if existing_invite:
            raise HTTPException(
                status_code=409,
                detail="A pending invitation for this email already exists.",
            )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        invitation = TenantInvitation(
            tenant_id=inviter.tenant_id,
            email=email,
            role=role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            invited_by_id=inviter.id,
            expires_at=datetime.now(UTC) + timedelta(hours=_INVITE_EXPIRY_HOURS),
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation, raw_token

    def accept_invite(
        self,
        raw_token: str,
        password: str,
        full_name: str | None,
    ) -> User:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        invitation = (
            self.db.query(TenantInvitation)
            .filter(
                TenantInvitation.token_hash == token_hash,
                TenantInvitation.status == InvitationStatus.PENDING.value,
            )
            .first()
        )

        if not invitation:
            raise HTTPException(
                status_code=400, detail="Invalid or already used invitation token."
            )

        if invitation.expires_at < datetime.now(UTC):
            invitation.status = InvitationStatus.EXPIRED.value
            self.db.commit()
            raise HTTPException(status_code=400, detail="Invitation token has expired.")

        existing_user = (
            self.db.query(User).filter(User.email == invitation.email).first()
        )

        if existing_user:
            if existing_user.tenant_id:
                raise HTTPException(
                    status_code=409,
                    detail="User already belongs to a tenant. Contact your admin.",
                )
            existing_user.tenant_id = invitation.tenant_id
            existing_user.role = invitation.role
            if full_name:
                existing_user.full_name = full_name
            user = existing_user
        else:
            user = User(
                email=invitation.email,
                full_name=full_name,
                hashed_password=hash_password(password),
                tenant_id=invitation.tenant_id,
                role=invitation.role,
            )
            self.db.add(user)

        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)
        return user

    def revoke_invite(self, invitation_id: uuid.UUID, tenant_id: uuid.UUID) -> TenantInvitation:
        invitation = (
            self.db.query(TenantInvitation)
            .filter(
                TenantInvitation.id == invitation_id,
                TenantInvitation.tenant_id == tenant_id,
                TenantInvitation.status == InvitationStatus.PENDING.value,
            )
            .first()
        )
        if not invitation:
            raise HTTPException(status_code=404, detail="Pending invitation not found.")
        invitation.status = InvitationStatus.REVOKED.value
        self.db.commit()
        self.db.refresh(invitation)
        return invitation
