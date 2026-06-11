import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.core.enums import UserRole


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: str = "analyst"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = [r.value for r in UserRole]
        if v not in valid:
            raise ValueError(f"Invalid role. Must be one of: {valid}")
        return v


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str | None = None


class InvitationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None
    # raw_token is included only in the create response
    invite_token: str | None = None

    model_config = {"from_attributes": True}
