"""API integration tests for compliance routes."""


class TestAuditExport:
    def test_export_json_returns_200(self, client, admin_headers):
        resp = client.post(
            "/api/v1/compliance/export-audit?format=json",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_export_csv_returns_200(self, client, admin_headers):
        resp = client.post(
            "/api/v1/compliance/export-audit?format=csv",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_json_body_is_list(self, client, admin_headers):
        resp = client.post(
            "/api/v1/compliance/export-audit?format=json",
            headers=admin_headers,
        )
        assert isinstance(resp.json(), list)

    def test_export_viewer_forbidden(self, client, viewer_headers):
        resp = client.post("/api/v1/compliance/export-audit", headers=viewer_headers)
        assert resp.status_code == 403

    def test_export_analyst_forbidden(self, client, analyst_headers):
        resp = client.post("/api/v1/compliance/export-audit", headers=analyst_headers)
        assert resp.status_code == 403

    def test_export_compliance_officer_allowed(self, client, compliance_headers):
        resp = client.post(
            "/api/v1/compliance/export-audit?format=json",
            headers=compliance_headers,
        )
        assert resp.status_code == 200

    def test_export_invalid_format_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/compliance/export-audit?format=xml",
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_export_requires_auth(self, client):
        resp = client.post("/api/v1/compliance/export-audit")
        assert resp.status_code == 401


class TestRetentionPolicy:
    def test_get_policy_default_when_not_set(self, client, admin_headers):
        resp = client.get("/api/v1/compliance/retention-policy", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["retention_days"] == 365
        assert data["auto_delete_enabled"] is False

    def test_put_policy_creates_record(self, client, admin_headers):
        resp = client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 180, "auto_delete_enabled": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retention_days"] == 180
        assert data["auto_delete_enabled"] is True

    def test_put_policy_updates_existing(self, client, admin_headers):
        client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 90},
            headers=admin_headers,
        )
        resp = client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 30},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["retention_days"] == 30

    def test_get_policy_after_put(self, client, admin_headers):
        client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 270},
            headers=admin_headers,
        )
        resp = client.get(
            "/api/v1/compliance/retention-policy",
            headers=admin_headers,
        )
        assert resp.json()["retention_days"] == 270

    def test_policy_viewer_forbidden(self, client, viewer_headers):
        resp = client.get(
            "/api/v1/compliance/retention-policy",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_policy_analyst_forbidden(self, client, analyst_headers):
        resp = client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 365},
            headers=analyst_headers,
        )
        assert resp.status_code == 403

    def test_policy_compliance_officer_allowed(self, client, compliance_headers):
        resp = client.get(
            "/api/v1/compliance/retention-policy",
            headers=compliance_headers,
        )
        assert resp.status_code == 200

    def test_retention_days_zero_rejected(self, client, admin_headers):
        resp = client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_retention_days_too_large_rejected(self, client, admin_headers):
        resp = client.put(
            "/api/v1/compliance/retention-policy",
            json={"retention_days": 9999},
            headers=admin_headers,
        )
        assert resp.status_code == 422
