from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    document_id: UUID
    question: str = Field(max_length=8000)
    conversation_id: UUID | None = None


class CitationResponse(BaseModel):
    chunk_id: UUID
    page: int | None
    section: str | None
    quote: str
    relevance_score: float


class AskResponse(BaseModel):
    answer: str
    grounded: bool
    needs_clarification: bool
    citations: list[CitationResponse]
    document_id: UUID
    conversation_id: UUID
    latency_ms: int