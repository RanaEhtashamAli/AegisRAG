"""API integration tests for tenant creation."""


def _register_and_token(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longenough123", "full_name": "Creator"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "longenough123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestCreateTenant:
    def test_create_tenant_happy_path_promotes_creator(self, client):
        headers = _register_and_token(client, "admin1@test.com")
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "Acme Corp", "slug": "acme-corp"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "acme-corp"

        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.json()["role"] == "tenant_admin"
        assert me.json()["tenant_id"] is not None

    def test_create_tenant_duplicate_slug_rejected(self, client):
        headers1 = _register_and_token(client, "admin2@test.com")
        client.post("/api/v1/tenants", json={"name": "First", "slug": "shared-slug"}, headers=headers1)

        headers2 = _register_and_token(client, "admin3@test.com")
        resp = client.post(
            "/api/v1/tenants", json={"name": "Second", "slug": "shared-slug"}, headers=headers2
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Tenant slug already taken."

    def test_create_tenant_user_already_has_tenant_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/tenants", json={"name": "New Org", "slug": "new-org"}, headers=admin_headers
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "User already belongs to a tenant."

    def test_create_tenant_invalid_slug_format_rejected(self, client):
        headers = _register_and_token(client, "admin4@test.com")
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "Bad Slug Co", "slug": "Not A Valid Slug!!"},
            headers=headers,
        )
        assert resp.status_code == 422
