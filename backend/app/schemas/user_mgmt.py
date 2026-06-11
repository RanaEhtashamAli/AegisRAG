import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.enums import UserRole


class TenantUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = [r.value for r in UserRole]
        if v not in valid:
            raise ValueError(f"Invalid role. Must be one of: {valid}")
        return v
