import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_user
from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    retrieved_doc_ids: str | None
    latency_ms: int | None
    created_at: str

    model_config = {"from_attributes": True}


def _session_to_response(session: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        message_count=len(session.messages) if session.messages is not None else 0,
    )


def _message_to_response(msg) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        retrieved_doc_ids=msg.retrieved_doc_ids,
        latency_ms=msg.latency_ms,
        created_at=msg.created_at.isoformat(),
    )


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> ChatSessionResponse:
    session = ChatService(db).create_session(user, body.title)
    return _session_to_response(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> list[ChatSessionResponse]:
    sessions = ChatService(db).list_sessions(user)
    return [_session_to_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> ChatSessionResponse:
    session = ChatService(db).get_session(session_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_session(
    session_id: uuid.UUID,
    body: ChatSessionRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> ChatSessionResponse:
    svc = ChatService(db)
    session = svc.get_session(session_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = svc.update_session_title(session, body.title)
    return _session_to_response(updated)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> None:
    if not ChatService(db).delete_session(session_id, user):
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> list[ChatMessageResponse]:
    svc = ChatService(db)
    session = svc.get_session(session_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return [_message_to_response(m) for m in session.messages]
