import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    event_type: str
    entity_type: str | None
    entity_id: str | None
    metadata_json: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
