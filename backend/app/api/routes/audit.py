import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_audit_view_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import AuditEventResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventResponse])
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_audit_view_permission()),
) -> list[AuditEventResponse]:
    return AuditService(db).get_events(
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
        entity_type=entity_type,
        user_id=user_id,
    )
