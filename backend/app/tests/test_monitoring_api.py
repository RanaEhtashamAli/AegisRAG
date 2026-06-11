"""API integration tests for monitoring routes."""
import uuid
from unittest.mock import AsyncMock, patch


class TestMonitoringHealth:
    def _health(self, client, headers, cache_ok=False, ollama_ok=False):
        with (
            patch("app.api.routes.monitoring.cache_service") as mock_cache,
            patch("app.api.routes.monitoring.model_router") as mock_router,
        ):
            mock_cache.stats.return_value = {"available": cache_ok}
            mock_router.health = AsyncMock(
                return_value={
                    "ollama": ollama_ok,
                    "vllm": None,
                    "vllm_enabled": False,
                }
            )
            return client.get("/api/v1/monitoring/health", headers=headers)

    def test_health_requires_admin(self, client, viewer_headers):
        resp = self._health(client, viewer_headers)
        assert resp.status_code == 403

    def test_health_analyst_forbidden(self, client, analyst_headers):
        resp = self._health(client, analyst_headers)
        assert resp.status_code == 403

    def test_health_returns_all_fields(self, client, admin_headers):
        resp = self._health(client, admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "db" in data
        assert "redis" in data
        assert "qdrant" in data
        assert "ollama" in data

    def test_health_db_is_true_when_test_db_up(self, client, admin_headers):
        resp = self._health(client, admin_headers)
        assert resp.json()["db"] is True

    def test_health_redis_false_when_unavailable(self, client, admin_headers):
        resp = self._health(client, admin_headers, cache_ok=False)
        assert resp.json()["redis"] is False


class TestMonitoringAlerts:
    def test_list_alerts_empty(self, client, admin_headers):
        resp = client.get("/api/v1/monitoring/alerts", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_alerts_returns_data(self, client, admin_headers, db, tenant, admin_user):
        from app.services.security_alert_service import SecurityAlertService
        SecurityAlertService(db).alert_prompt_injection(tenant.id, admin_user.id, "inject")
        db.flush()
        resp = client.get("/api/v1/monitoring/alerts", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_resolve_alert(self, client, admin_headers, db, tenant, admin_user):
        from app.services.security_alert_service import SecurityAlertService
        svc = SecurityAlertService(db)
        svc.alert_prompt_injection(tenant.id, admin_user.id, "inject")
        db.flush()
        alert = svc.list_alerts(tenant.id)[0]
        resp = client.patch(
            f"/api/v1/monitoring/alerts/{alert.id}/resolve",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["resolved"] is True

    def test_resolve_nonexistent_alert_404(self, client, admin_headers):
        resp = client.patch(
            f"/api/v1/monitoring/alerts/{uuid.uuid4()}/resolve",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_alerts_analyst_forbidden(self, client, analyst_headers):
        resp = client.get("/api/v1/monitoring/alerts", headers=analyst_headers)
        assert resp.status_code == 403

    def test_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/monitoring/alerts")
        assert resp.status_code == 401


class TestMonitoringUsage:
    def test_usage_totals_returns_zeros_when_empty(self, client, admin_headers):
        resp = client.get("/api/v1/monitoring/usage", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queries"] == 0
        assert data["total_tokens"] == 0

    def test_usage_history_returns_list(self, client, admin_headers):
        resp = client.get("/api/v1/monitoring/usage/history", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_usage_history_custom_days(self, client, admin_headers):
        resp = client.get(
            "/api/v1/monitoring/usage/history?days=7",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_usage_viewer_forbidden(self, client, viewer_headers):
        resp = client.get("/api/v1/monitoring/usage", headers=viewer_headers)
        assert resp.status_code == 403

    def test_usage_analyst_forbidden(self, client, analyst_headers):
        resp = client.get("/api/v1/monitoring/usage", headers=analyst_headers)
        assert resp.status_code == 403


class TestMonitoringCacheStats:
    def test_cache_stats_returns_fields(self, client, admin_headers):
        with patch("app.api.routes.monitoring.cache_service") as mock_cache:
            mock_cache.stats.return_value = {
                "available": False,
                "used_memory_human": None,
                "connected_clients": None,
            }
            resp = client.get("/api/v1/monitoring/cache-stats", headers=admin_headers)
        assert resp.status_code == 200
        assert "available" in resp.json()

    def test_cache_stats_analyst_forbidden(self, client, analyst_headers):
        resp = client.get("/api/v1/monitoring/cache-stats", headers=analyst_headers)
        assert resp.status_code == 403

    def test_cache_stats_requires_auth(self, client):
        resp = client.get("/api/v1/monitoring/cache-stats")
        assert resp.status_code == 401
