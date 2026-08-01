"""API integration tests for auth registration."""


class TestRegister:
    def test_register_happy_path_returns_viewer(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@test.com", "password": "longenough123", "full_name": "New User"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@test.com"
        assert body["role"] == "viewer"
        assert body["tenant_id"] is None

    def test_register_duplicate_email_rejected(self, client):
        payload = {"email": "dupe@test.com", "password": "longenough123", "full_name": "Dupe"}
        first = client.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201
        second = client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 400
        assert second.json()["detail"] == "Email already registered."

    def test_register_password_too_short_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "shortpw@test.com", "password": "short", "full_name": "Short"},
        )
        assert resp.status_code == 422
