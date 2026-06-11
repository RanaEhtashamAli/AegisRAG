"""API integration tests for document routes."""
import io
import uuid
from unittest.mock import MagicMock, patch


def _make_doc(db, tenant_id, uploaded_by_id, *, classification="internal", filename="test.pdf"):
    """Insert a Document row directly — bypasses file I/O."""
    from app.models.document import Document
    doc = Document(
        tenant_id=tenant_id,
        uploaded_by_id=uploaded_by_id,
        filename=f"{uuid.uuid4()}.pdf",
        original_filename=filename,
        content_type="application/pdf",
        file_path="/tmp/nonexistent.pdf",
        checksum="abc" + uuid.uuid4().hex,
        status="indexed",
        classification=classification,
    )
    db.add(doc)
    db.flush()
    return doc


class TestDocumentUpload:
    def test_upload_requires_auth(self, client):
        resp = client.post("/api/v1/documents/upload")
        assert resp.status_code == 401

    def test_upload_viewer_forbidden(self, client, viewer_headers):
        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
        with patch("app.api.routes.documents.process_document"):
            resp = client.post(
                "/api/v1/documents/upload",
                data={"classification": "internal"},
                files=files,
                headers=viewer_headers,
            )
        assert resp.status_code == 403

    def test_upload_admin_creates_document_and_queues_task(
        self, client, admin_headers
    ):
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.status = "uploaded"
        mock_doc.original_filename = "report.pdf"
        mock_doc.checksum = "abc123"
        mock_doc.classification = "internal"

        with (
            patch("app.api.routes.documents.DocumentService") as mock_doc_svc,
            patch("app.api.routes.documents.process_document") as mock_task,
        ):
            mock_doc_svc.return_value.save_upload.return_value = mock_doc
            resp = client.post(
                "/api/v1/documents/upload",
                data={"classification": "internal"},
                files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                headers=admin_headers,
            )

        assert resp.status_code == 202
        mock_task.delay.assert_called_once_with(str(mock_doc.id))

    def test_upload_analyst_allowed(self, client, analyst_headers):
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.status = "uploaded"
        mock_doc.original_filename = "data.pdf"
        mock_doc.checksum = "xyz"
        mock_doc.classification = "internal"

        with (
            patch("app.api.routes.documents.DocumentService") as mock_doc_svc,
            patch("app.api.routes.documents.process_document"),
        ):
            mock_doc_svc.return_value.save_upload.return_value = mock_doc
            resp = client.post(
                "/api/v1/documents/upload",
                data={"classification": "internal"},
                files={"file": ("data.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                headers=analyst_headers,
            )
        assert resp.status_code == 202


class TestDocumentList:
    def test_list_returns_tenant_documents(self, client, admin_headers, db, admin_user, tenant):
        _make_doc(db, tenant.id, admin_user.id, classification="internal")
        _make_doc(db, tenant.id, admin_user.id, classification="public")
        resp = client.get("/api/v1/documents", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_viewer_cannot_see_confidential(
        self, client, viewer_headers, db, viewer_user, tenant
    ):
        _make_doc(db, tenant.id, viewer_user.id, classification="public")
        _make_doc(db, tenant.id, viewer_user.id, classification="confidential")
        resp = client.get("/api/v1/documents", headers=viewer_headers)
        assert resp.status_code == 200
        classifications = {d["classification"] for d in resp.json()}
        assert "confidential" not in classifications

    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 401


class TestDocumentGet:
    def test_get_existing_document(self, client, admin_headers, db, admin_user, tenant):
        doc = _make_doc(db, tenant.id, admin_user.id)
        resp = client.get(f"/api/v1/documents/{doc.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(doc.id)

    def test_get_nonexistent_returns_404(self, client, admin_headers):
        resp = client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=admin_headers)
        assert resp.status_code == 404

    def test_viewer_cannot_get_restricted_document(
        self, client, viewer_headers, db, viewer_user, tenant
    ):
        doc = _make_doc(db, tenant.id, viewer_user.id, classification="restricted")
        resp = client.get(f"/api/v1/documents/{doc.id}", headers=viewer_headers)
        assert resp.status_code == 403

    def test_get_requires_auth(self, client, db, tenant):
        resp = client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 401


class TestDocumentDelete:
    def test_delete_requires_admin(
        self, client, analyst_headers, db, analyst_user, tenant
    ):
        doc = _make_doc(db, tenant.id, analyst_user.id)
        resp = client.delete(f"/api/v1/documents/{doc.id}", headers=analyst_headers)
        assert resp.status_code == 403

    def test_viewer_cannot_delete(
        self, client, viewer_headers, db, viewer_user, tenant
    ):
        doc = _make_doc(db, tenant.id, viewer_user.id)
        resp = client.delete(f"/api/v1/documents/{doc.id}", headers=viewer_headers)
        assert resp.status_code == 403

    def test_admin_can_delete(self, client, admin_headers, db, admin_user, tenant):
        doc = _make_doc(db, tenant.id, admin_user.id)
        # Qdrant delete will fail (not running) but is wrapped in try/except
        resp = client.delete(f"/api/v1/documents/{doc.id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, admin_headers):
        resp = client.delete(f"/api/v1/documents/{uuid.uuid4()}", headers=admin_headers)
        assert resp.status_code == 404
