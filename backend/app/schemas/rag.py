import uuid

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    session_id: uuid.UUID | None = None  # optional chat session for history + persistence


class SourceReference(BaseModel):
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    score: float
    text_preview: str


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    warning: str | None = None


class RAGStreamEvent(BaseModel):
    type: str  # "sources" | "token" | "done" | "error"
    content: str | None = None
    sources: list[SourceReference] | None = None
