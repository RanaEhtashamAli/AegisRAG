from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RetentionPolicyRequest(BaseModel):
    retention_days: int = Field(ge=1, le=3650, default=365)
    auto_delete_enabled: bool = False


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    retention_days: int
    auto_delete_enabled: bool
    created_at: datetime | None
    updated_at: datetime | None
