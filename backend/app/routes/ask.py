import logging
import re
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Citation, Conversation, Document, Message
from app.rag.qa import (
    GroqUnavailableError,
    InvalidModelAnswerError,
    StructuredAnswer,
    generate_answer,
)
from app.rag.retrieval import RetrievedChunk, has_sufficient_evidence, retrieve_document_chunks
from app.schemas.qa import AskRequest, AskResponse, CitationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["questions"])
INSUFFICIENT_EVIDENCE_ANSWER = "The policy does not provide enough information to answer this question."
QUOTE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    started_at = perf_counter()
    question = request.question.strip()
    if not question:
        raise HTTPException(400, "Question must not be empty.")

    document = db.get(Document, request.document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    if document.status != "indexed":
        raise HTTPException(409, f"Document is not ready for questions (status: {document.status}).")

    conversation = _load_conversation(db, request.conversation_id, document.id)
    retrieved = retrieve_document_chunks(db, document.id, question)
    if has_sufficient_evidence(question, retrieved):
        try:
            model_answer = generate_answer(question, retrieved)
            retrieved_ids = {item.chunk.id for item in retrieved}
            if any(chunk_id not in retrieved_ids for chunk_id in model_answer.used):
                raise InvalidModelAnswerError("Groq referenced a chunk outside the supplied evidence.")
        except GroqUnavailableError as error:
            status_code = 503 if not settings.groq_api_key else 502
            raise HTTPException(status_code, "The answer service is temporarily unavailable.") from error
        except InvalidModelAnswerError as error:
            raise HTTPException(502, "The answer service returned an invalid response.") from error
    else:
        model_answer = StructuredAnswer(
            answer=INSUFFICIENT_EVIDENCE_ANSWER,
            used=[],
            grounded=False,
            needs_clarification=False,
        )

    latency_ms = int((perf_counter() - started_at) * 1000)
    citations = _build_citations(model_answer, retrieved, question)
    conversation = _save_exchange(
        db=db,
        conversation=conversation,
        document_id=document.id,
        question=question,
        answer=model_answer.answer,
        latency_ms=latency_ms,
        citations=citations,
    )
    logger.info(
        "Answered question for document %s using %s citations (%s ms)",
        document.id,
        len(citations),
        latency_ms,
    )
    return AskResponse(
        answer=model_answer.answer,
        grounded=model_answer.grounded,
        needs_clarification=model_answer.needs_clarification,
        citations=[citation[1] for citation in citations],
        document_id=document.id,
        conversation_id=conversation.id,
        latency_ms=latency_ms,
    )


def _load_conversation(
    db: Session, conversation_id: UUID | None, document_id: UUID
) -> Conversation | None:
    if conversation_id is None:
        return None
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    if conversation.document_id is not None and conversation.document_id != document_id:
        raise HTTPException(409, "Conversation belongs to a different document.")
    return conversation


def _build_citations(
    answer: StructuredAnswer, retrieved: list[RetrievedChunk], question: str
) -> list[tuple[Citation, CitationResponse]]:
    if not answer.grounded:
        return []
    retrieved_by_id = {item.chunk.id: item for item in retrieved}
    citations: list[tuple[Citation, CitationResponse]] = []
    for chunk_id in answer.used:
        item = retrieved_by_id[chunk_id]
        quote = _select_quote(item.chunk.text, question)
        citation = Citation(
            chunk_id=item.chunk.id,
            quoted_text=quote,
            relevance_score=item.relevance_score,
        )
        citations.append(
            (
                citation,
                CitationResponse(
                    chunk_id=item.chunk.id,
                    page=item.chunk.page,
                    section=item.chunk.section,
                    quote=quote,
                    relevance_score=item.relevance_score,
                ),
            )
        )
    return citations


def _select_quote(text: str, question: str) -> str:
    terms = set(QUOTE_TOKEN_PATTERN.findall(question.lower()))
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    best_sentence = max(
        enumerate(sentences),
        key=lambda entry: (
            len(terms & set(QUOTE_TOKEN_PATTERN.findall(entry[1].lower()))),
            -entry[0],
        ),
    )[1]
    return best_sentence[:320].rstrip()


def _save_exchange(
    db: Session,
    conversation: Conversation | None,
    document_id: UUID,
    question: str,
    answer: str,
    latency_ms: int,
    citations: list[tuple[Citation, CitationResponse]],
) -> Conversation:
    if conversation is None:
        conversation = Conversation(document_id=document_id, title=question[:512])
        db.add(conversation)
        db.flush()
    elif conversation.document_id is None:
        conversation.document_id = document_id

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        latency_ms=latency_ms,
    )
    db.add_all(
        [
            Message(conversation_id=conversation.id, role="user", content=question),
            assistant_message,
        ]
    )
    db.flush()
    for citation, _ in citations:
        citation.message_id = assistant_message.id
        db.add(citation)
    db.commit()
    db.refresh(conversation)
    return conversation