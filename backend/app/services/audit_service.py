import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        event_type: str,
        user_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events(
        self,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        entity_type: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[AuditEvent]:
        q = (
            self.db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == tenant_id)
        )
        if event_type:
            q = q.filter(AuditEvent.event_type == event_type)
        if entity_type:
            q = q.filter(AuditEvent.entity_type == entity_type)
        if user_id:
            q = q.filter(AuditEvent.user_id == user_id)
        return q.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()
