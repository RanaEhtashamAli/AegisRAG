"""Compliance routes — audit export and document retention policy management.

Access is restricted to tenant_admin and compliance_officer roles.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_audit_view_permission
from app.db.session import get_db
from app.models.document_retention_policy import DocumentRetentionPolicy
from app.models.user import User
from app.schemas.compliance import RetentionPolicyRequest, RetentionPolicyResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _admin_or_compliance(user: User = Depends(require_audit_view_permission())):
    return user


# ── Audit export ─────────────────────────────────────────────────────────────


@router.post("/export-audit")
def export_audit(
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    since: date | None = None,
    until: date | None = None,
    event_type: str | None = None,
    limit: int = 1000,
    user: User = Depends(_admin_or_compliance),
    db: Session = Depends(get_db),
):
    """Export audit events for the tenant as JSON or CSV."""
    svc = AuditService(db)
    events = svc.get_events(
        tenant_id=user.tenant_id,
        limit=min(limit, 10000),
        event_type=event_type,
    )

    # Apply date range filter if provided
    def _in_range(ev) -> bool:
        if since and ev.created_at.date() < since:
            return False
        if until and ev.created_at.date() > until:
            return False
        return True

    events = [e for e in events if _in_range(e)]

    if format == "json":
        payload = [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "user_id": str(e.user_id) if e.user_id else None,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "metadata": e.metadata_json,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_export.json"},
        )

    # CSV format
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "event_type", "user_id", "entity_type",
            "entity_id", "ip_address", "created_at",
        ],
    )
    writer.writeheader()
    for e in events:
        writer.writerow(
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "user_id": str(e.user_id) if e.user_id else "",
                "entity_type": e.entity_type or "",
                "entity_id": e.entity_id or "",
                "ip_address": e.ip_address or "",
                "created_at": e.created_at.isoformat(),
            }
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )


# ── Retention policy ──────────────────────────────────────────────────────────


@router.get("/retention-policy", response_model=RetentionPolicyResponse)
def get_retention_policy(
    user: User = Depends(_admin_or_compliance),
    db: Session = Depends(get_db),
) -> RetentionPolicyResponse:
    policy = (
        db.query(DocumentRetentionPolicy)
        .filter(DocumentRetentionPolicy.tenant_id == user.tenant_id)
        .first()
    )
    if not policy:
        return RetentionPolicyResponse(
            tenant_id=user.tenant_id,
            retention_days=365,
            auto_delete_enabled=False,
            created_at=None,
            updated_at=None,
        )
    return RetentionPolicyResponse.model_validate(policy)


@router.put("/retention-policy", response_model=RetentionPolicyResponse)
def upsert_retention_policy(
    data: RetentionPolicyRequest,
    user: User = Depends(_admin_or_compliance),
    db: Session = Depends(get_db),
) -> RetentionPolicyResponse:
    policy = (
        db.query(DocumentRetentionPolicy)
        .filter(DocumentRetentionPolicy.tenant_id == user.tenant_id)
        .first()
    )
    if policy:
        policy.retention_days = data.retention_days
        policy.auto_delete_enabled = data.auto_delete_enabled
        policy.updated_at = datetime.now(UTC)
    else:
        policy = DocumentRetentionPolicy(
            tenant_id=user.tenant_id,
            retention_days=data.retention_days,
            auto_delete_enabled=data.auto_delete_enabled,
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    return RetentionPolicyResponse.model_validate(policy)
