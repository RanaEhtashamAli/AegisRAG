"""DB integration tests for SecurityAlertService."""
import uuid

from app.services.security_alert_service import SecurityAlertService


def _other_tenant(db):
    from app.models.tenant import Tenant
    t = Tenant(name="Other Corp", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(t)
    db.flush()
    return t


class TestSecurityAlertService:
    def test_prompt_injection_alert_created(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "jailbreak")
        alerts = svc.list_alerts(tenant.id)
        assert len(alerts) == 1
        assert alerts[0].event_type == "security.prompt_injection_attempt"
        assert alerts[0].severity == "medium"

    def test_restricted_access_alert_created(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_restricted_access_attempt(tenant.id, admin_user.id, "doc-123")
        alerts = svc.list_alerts(tenant.id)
        assert len(alerts) == 1
        assert alerts[0].event_type == "security.restricted_access_attempt"

    def test_list_alerts_unresolved_by_default(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "jailbreak")
        assert len(svc.list_alerts(tenant.id, resolved=False)) == 1

    def test_list_alerts_resolved_filter(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "jailbreak")
        alert = svc.list_alerts(tenant.id)[0]
        svc.resolve(alert.id, tenant.id)
        assert len(svc.list_alerts(tenant.id, resolved=False)) == 0
        assert len(svc.list_alerts(tenant.id, resolved=True)) == 1

    def test_resolve_returns_true(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "inject")
        alert = svc.list_alerts(tenant.id)[0]
        assert svc.resolve(alert.id, tenant.id) is True

    def test_resolve_nonexistent_returns_false(self, db, tenant):
        assert SecurityAlertService(db).resolve(uuid.uuid4(), tenant.id) is False

    def test_resolve_wrong_tenant_returns_false(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "inject")
        alert = svc.list_alerts(tenant.id)[0]
        assert svc.resolve(alert.id, uuid.uuid4()) is False

    def test_list_alerts_empty_when_none(self, db, tenant):
        assert SecurityAlertService(db).list_alerts(tenant.id) == []

    def test_list_alerts_limit(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        for i in range(10):
            svc.alert_prompt_injection(tenant.id, admin_user.id, f"pattern-{i}")
        assert len(svc.list_alerts(tenant.id, limit=3)) == 3

    def test_list_alerts_excludes_other_tenant(self, db, tenant, admin_user):
        other = _other_tenant(db)
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "inject")
        assert len(svc.list_alerts(other.id)) == 0

    def test_resolved_at_set_on_resolve(self, db, tenant, admin_user):
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "inject")
        alert = svc.list_alerts(tenant.id)[0]
        svc.resolve(alert.id, tenant.id)
        resolved = svc.list_alerts(tenant.id, resolved=True)[0]
        assert resolved.resolved_at is not None
