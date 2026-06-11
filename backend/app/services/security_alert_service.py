"""Security alert generation and management.

Generates alerts for:
- Repeated authentication failures (brute-force detection)
- Restricted document access attempts
- Prompt injection attempts
- Abnormal query volume per tenant
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.audit_event import AuditEvent
from app.models.security_alert import SecurityAlert
from app.services.metrics_service import security_alerts_total


class SecurityAlertService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _create(
        self,
        tenant_id: uuid.UUID,
        severity: str,
        event_type: str,
        description: str,
        metadata: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> SecurityAlert:
        alert = SecurityAlert(
            tenant_id=tenant_id,
            user_id=user_id,
            severity=severity,
            event_type=event_type,
            description=description,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.db.add(alert)
        self.db.commit()
        security_alerts_total.labels(severity=severity, event_type=event_type).inc()
        logger.warning(
            "security_alert_created",
            tenant_id=str(tenant_id),
            severity=severity,
            event_type=event_type,
        )
        return alert

    def check_failed_logins(self, email: str, ip_address: str | None) -> None:
        """Create a high-severity alert if login failures exceed the threshold."""
        window_start = datetime.now(UTC) - timedelta(
            minutes=settings.FAILED_LOGIN_WINDOW_MINUTES
        )
        count = (
            self.db.query(func.count(AuditEvent.id))
            .filter(
                AuditEvent.event_type == "auth.login_failed",
                AuditEvent.created_at >= window_start,
                AuditEvent.metadata_json.contains(email),
            )
            .scalar()
            or 0
        )
        if count >= settings.FAILED_LOGIN_ALERT_THRESHOLD:
            existing = (
                self.db.query(SecurityAlert)
                .filter(
                    SecurityAlert.event_type == "auth.brute_force_detected",
                    SecurityAlert.resolved == False,  # noqa: E712
                    SecurityAlert.metadata_json.contains(email),
                )
                .first()
            )
            if not existing:
                self._create(
                    tenant_id=uuid.UUID(int=0),  # no tenant context for auth failures
                    severity="high",
                    event_type="auth.brute_force_detected",
                    description=f"Repeated login failures for {email}: {count} in {settings.FAILED_LOGIN_WINDOW_MINUTES}m",
                    metadata={"email": email, "ip_address": ip_address, "failure_count": count},
                )

    def alert_prompt_injection(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, pattern: str
    ) -> None:
        self._create(
            tenant_id=tenant_id,
            user_id=user_id,
            severity="medium",
            event_type="security.prompt_injection_attempt",
            description="Prompt injection attempt detected and blocked",
            metadata={"matched_pattern": pattern},
        )

    def alert_restricted_access_attempt(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, document_id: str
    ) -> None:
        self._create(
            tenant_id=tenant_id,
            user_id=user_id,
            severity="medium",
            event_type="security.restricted_access_attempt",
            description="User attempted to access a restricted document without permission",
            metadata={"document_id": document_id},
        )

    def check_query_rate(self, tenant_id: uuid.UUID) -> None:
        """Alert if a tenant exceeds the hourly query threshold."""
        window_start = datetime.now(UTC) - timedelta(hours=1)
        count = (
            self.db.query(func.count(AuditEvent.id))
            .filter(
                AuditEvent.event_type == "rag.query",
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.created_at >= window_start,
            )
            .scalar()
            or 0
        )
        if count > settings.SUSPICIOUS_QUERY_RATE_THRESHOLD:
            existing = (
                self.db.query(SecurityAlert)
                .filter(
                    SecurityAlert.tenant_id == tenant_id,
                    SecurityAlert.event_type == "security.abnormal_query_volume",
                    SecurityAlert.resolved == False,  # noqa: E712
                    SecurityAlert.created_at >= window_start,
                )
                .first()
            )
            if not existing:
                self._create(
                    tenant_id=tenant_id,
                    severity="low",
                    event_type="security.abnormal_query_volume",
                    description=f"Tenant made {count} queries in the last hour (threshold: {settings.SUSPICIOUS_QUERY_RATE_THRESHOLD})",
                    metadata={"query_count": count, "threshold": settings.SUSPICIOUS_QUERY_RATE_THRESHOLD},
                )

    def list_alerts(
        self,
        tenant_id: uuid.UUID,
        resolved: bool = False,
        limit: int = 50,
    ) -> list[SecurityAlert]:
        return (
            self.db.query(SecurityAlert)
            .filter(
                SecurityAlert.tenant_id == tenant_id,
                SecurityAlert.resolved == resolved,
            )
            .order_by(SecurityAlert.created_at.desc())
            .limit(limit)
            .all()
        )

    def resolve(self, alert_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        alert = (
            self.db.query(SecurityAlert)
            .filter(SecurityAlert.id == alert_id, SecurityAlert.tenant_id == tenant_id)
            .first()
        )
        if not alert:
            return False
        alert.resolved = True
        alert.resolved_at = datetime.now(UTC)
        self.db.commit()
        return True
