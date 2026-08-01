"""RBAC unit tests — no database required."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.enums import Classification, UserRole
from app.core.permissions import can_access_document, get_allowed_classifications


def _make_user(role: str, user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.role = role
    user.tenant_id = uuid.uuid4()
    user.is_active = True
    return user


def _make_doc(classification: str, uploaded_by_id: uuid.UUID | None = None) -> MagicMock:
    doc = MagicMock()
    doc.classification = classification
    doc.uploaded_by_id = uploaded_by_id or uuid.uuid4()
    return doc


# ---------------------------------------------------------------------------
# get_allowed_classifications
# ---------------------------------------------------------------------------


def test_tenant_admin_gets_all_classifications():
    user = _make_user(UserRole.TENANT_ADMIN.value)
    allowed = get_allowed_classifications(user)
    assert set(allowed) == {"public", "internal", "confidential", "restricted"}


def test_compliance_officer_gets_all_classifications():
    user = _make_user(UserRole.COMPLIANCE_OFFICER.value)
    allowed = get_allowed_classifications(user)
    assert set(allowed) == {"public", "internal", "confidential", "restricted"}


def test_analyst_gets_public_internal_confidential():
    user = _make_user(UserRole.ANALYST.value)
    allowed = get_allowed_classifications(user)
    assert set(allowed) == {"public", "internal", "confidential"}
    assert "restricted" not in allowed


def test_viewer_gets_public_internal_only():
    user = _make_user(UserRole.VIEWER.value)
    allowed = get_allowed_classifications(user)
    assert set(allowed) == {"public", "internal"}
    assert "confidential" not in allowed
    assert "restricted" not in allowed


# ---------------------------------------------------------------------------
# can_access_document
# ---------------------------------------------------------------------------


def test_viewer_can_access_public_document():
    user = _make_user(UserRole.VIEWER.value)
    doc = _make_doc("public")
    assert can_access_document(user, doc) is True


def test_viewer_cannot_access_confidential_document():
    user = _make_user(UserRole.VIEWER.value)
    doc = _make_doc("confidential")
    assert can_access_document(user, doc) is False


def test_viewer_cannot_access_restricted_document():
    user = _make_user(UserRole.VIEWER.value)
    doc = _make_doc("restricted")
    assert can_access_document(user, doc) is False


def test_analyst_cannot_access_restricted_document():
    user = _make_user(UserRole.ANALYST.value)
    doc = _make_doc("restricted")
    assert can_access_document(user, doc) is False


def test_analyst_cannot_access_own_restricted_document():
    user_id = uuid.uuid4()
    user = _make_user(UserRole.ANALYST.value, user_id=user_id)
    doc = _make_doc("restricted", uploaded_by_id=user_id)
    assert can_access_document(user, doc) is False


def test_analyst_can_access_confidential_document():
    user = _make_user(UserRole.ANALYST.value)
    doc = _make_doc("confidential")
    assert can_access_document(user, doc) is True


def test_compliance_officer_can_access_restricted_document():
    user = _make_user(UserRole.COMPLIANCE_OFFICER.value)
    doc = _make_doc("restricted")
    assert can_access_document(user, doc) is True


def test_tenant_admin_can_access_all_classifications():
    user = _make_user(UserRole.TENANT_ADMIN.value)
    for cls in Classification:
        doc = _make_doc(cls.value)
        assert can_access_document(user, doc) is True, f"Admin should access {cls.value}"


# ---------------------------------------------------------------------------
# Tenant isolation guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_service_passes_allowed_classifications(monkeypatch):
    """Verify RAGService always calls qdrant_service.search with allowed_classifications."""
    from unittest.mock import AsyncMock

    from app.services import rag_service as rag_module
    from app.services.inference.base_provider import InferenceRequest, InferenceResponse

    captured: dict = {}

    def fake_search(query_vector, tenant_id, allowed_classifications, top_k):
        captured["tenant_id"] = tenant_id
        captured["allowed_classifications"] = allowed_classifications
        return []

    def fake_embed(text):
        return [0.0] * 384

    mock_provider = MagicMock()
    mock_provider.provider_name = "ollama"
    mock_provider.generate = AsyncMock(
        return_value=InferenceResponse(content="answer", model="test", prompt_tokens=0, completion_tokens=0)
    )
    mock_request = InferenceRequest(model="llama3.1:8b", prompt="test")

    monkeypatch.setattr(rag_module.qdrant_service, "search", fake_search)
    monkeypatch.setattr(rag_module.embedding_service, "embed_text", fake_embed)
    monkeypatch.setattr(
        rag_module.model_router,
        "build_request",
        lambda **kw: (mock_provider, mock_request),
    )

    db_mock = MagicMock()

    monkeypatch.setattr(
        "app.services.rag_service.AuditService",
        lambda db: MagicMock(log=MagicMock()),
    )
    monkeypatch.setattr(
        "app.services.rag_service.UsageMetricsService",
        lambda db: MagicMock(record_query=MagicMock()),
    )
    monkeypatch.setattr(
        "app.services.rag_service.ChatService",
        lambda db: MagicMock(get_context_messages=MagicMock(return_value=[])),
    )

    user = _make_user(UserRole.VIEWER.value)
    user.tenant_id = uuid.uuid4()

    from app.services.rag_service import RAGService

    svc = RAGService(db_mock)
    await svc.query("test question", top_k=3, user=user)

    assert captured["tenant_id"] == str(user.tenant_id)
    # Viewer should only be allowed public and internal
    assert set(captured["allowed_classifications"]) == {"public", "internal"}
