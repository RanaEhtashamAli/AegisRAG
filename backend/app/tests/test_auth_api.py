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


def _register_and_login(client, email="refresh-user@test.com"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longenough123", "full_name": "Refresh User"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "longenough123"}
    )
    return login.json()


class TestLoginTokens:
    def test_login_returns_access_and_refresh_tokens(self, client):
        body = _register_and_login(client, "login-tokens@test.com")
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"


class TestRefreshToken:
    def test_refresh_issues_new_tokens(self, client):
        body = _register_and_login(client, "refresh-ok@test.com")
        resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
        )
        assert resp.status_code == 200
        new_body = resp.json()
        assert new_body["access_token"]
        assert new_body["refresh_token"]
        assert new_body["refresh_token"] != body["refresh_token"]

    def test_reusing_rotated_refresh_token_rejected(self, client):
        body = _register_and_login(client, "refresh-reuse@test.com")
        first = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
        )
        assert first.status_code == 200

        # The original token was rotated out by the call above — reusing it must fail.
        second = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
        )
        assert second.status_code == 401

    def test_invalid_refresh_token_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh_token(self, client):
        body = _register_and_login(client, "logout-user@test.com")
        logout_resp = client.post(
            "/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}
        )
        assert logout_resp.status_code == 204

        refresh_resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
        )
        assert refresh_resp.status_code == 401

    def test_logout_nonexistent_token_does_not_error(self, client):
        resp = client.post(
            "/api/v1/auth/logout", json={"refresh_token": "never-existed"}
        )
        assert resp.status_code == 204
