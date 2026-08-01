"""API integration tests for chat session rename."""


class TestRenameSession:
    def test_rename_session_updates_title(self, client, admin_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "New Chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": "Renamed Chat"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed Chat"

    def test_rename_other_users_session_rejected(self, client, admin_headers, analyst_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "Admin's chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": "Hijacked"},
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    def test_rename_empty_title_rejected(self, client, admin_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "New Chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": ""},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_rename_nonexistent_session_returns_404(self, client, admin_headers):
        resp = client.patch(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
            json={"title": "Doesn't matter"},
            headers=admin_headers,
        )
        assert resp.status_code == 404
