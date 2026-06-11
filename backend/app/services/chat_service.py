from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, user: User, title: str = "New Chat") -> ChatSession:
        session = ChatSession(
            tenant_id=user.tenant_id,
            user_id=user.id,
            title=title,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, user: User) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.tenant_id == user.tenant_id,
                ChatSession.user_id == user.id,
            )
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def get_session(self, session_id: uuid.UUID, user: User) -> ChatSession | None:
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == session_id,
                ChatSession.tenant_id == user.tenant_id,
                ChatSession.user_id == user.id,
            )
            .first()
        )

    def delete_session(self, session_id: uuid.UUID, user: User) -> bool:
        session = self.get_session(session_id, user)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        retrieved_doc_ids: list[str] | None = None,
        latency_ms: int | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            retrieved_doc_ids=json.dumps(retrieved_doc_ids) if retrieved_doc_ids else None,
            latency_ms=latency_ms,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_context_messages(self, session_id: uuid.UUID) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(settings.CHAT_SESSION_MAX_MESSAGES)
            .all()
        )

    def update_session_title(self, session: ChatSession, title: str) -> ChatSession:
        session.title = title[:255]
        self.db.commit()
        self.db.refresh(session)
        return session
