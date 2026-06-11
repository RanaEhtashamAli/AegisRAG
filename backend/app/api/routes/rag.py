from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_user
from app.core.permissions import require_audit_view_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
def rag_query(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> RAGQueryResponse:
    return RAGService(db).query(request.question, request.top_k, user, request.session_id)


@router.post("/query-stream")
async def rag_query_stream(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> StreamingResponse:
    """SSE streaming endpoint. Each event is a JSON object prefixed with 'data: '."""
    svc = RAGService(db)

    async def event_generator():
        async for chunk in svc.query_stream(
            request.question, request.top_k, user, request.session_id
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/debug-query")
def rag_debug_query(
    question: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(require_audit_view_permission()),
) -> dict:
    """Detailed retrieval debug info — admin/compliance_officer only."""
    return RAGService(db).debug_query(question, top_k, user)
