import re
from dataclasses import dataclass
from uuid import UUID

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk

RRF_K = 60
TOP_K = 5
MIN_QUERY_TERM_COVERAGE = 0.25
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
QUERY_STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "available", "be", "been", "being", "but",
    "by", "describe", "did", "do", "does", "for", "from", "how", "in", "into", "is",
    "it", "of", "on", "or", "please", "policy", "tell", "that", "the", "these", "this", "those",
    "to", "type", "types", "what", "when", "where", "which", "who", "why", "with", "would",
}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    relevance_score: float
    matched_query_terms: int
    query_term_coverage: float


def retrieve_document_chunks(
    db: Session, document_id: UUID, question: str, top_k: int = TOP_K
) -> list[RetrievedChunk]:
    chunks = list(
        db.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
    )
    if not chunks:
        return []

    query_tokens = _tokens(question)
    if not query_tokens:
        return []

    texts = [chunk.text for chunk in chunks]
    tfidf_scores = [0.0] * len(chunks)
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        matrix = vectorizer.fit_transform(texts)
        tfidf_scores = cosine_similarity(vectorizer.transform([question]), matrix)[0].tolist()
    except ValueError:
        pass

    tokenized_chunks = [_tokens(text) for text in texts]
    bm25_scores = BM25Okapi(tokenized_chunks).get_scores(query_tokens).tolist()
    fused_scores: dict[int, float] = {}

    tfidf_ranking = sorted(
        (index for index, score in enumerate(tfidf_scores) if score > 0),
        key=lambda index: (-tfidf_scores[index], index),
    )
    query_token_set = set(query_tokens)
    bm25_ranking = sorted(
        (index for index, tokens in enumerate(tokenized_chunks) if query_token_set & set(tokens)),
        key=lambda index: (-bm25_scores[index], index),
    )
    for ranking in (tfidf_ranking, bm25_ranking):
        for rank, index in enumerate(ranking, start=1):
            fused_scores[index] = fused_scores.get(index, 0.0) + 1.0 / (RRF_K + rank)

    if not fused_scores:
        return []

    query_terms = set(query_tokens) - QUERY_STOP_WORDS
    maximum_score = max(fused_scores.values())
    results: list[RetrievedChunk] = []
    for index, score in sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]:
        chunk_terms = set(_tokens(chunks[index].text))
        matched_terms = len(query_terms & chunk_terms)
        coverage = matched_terms / len(query_terms) if query_terms else 0.0
        results.append(
            RetrievedChunk(
                chunk=chunks[index],
                relevance_score=score / maximum_score,
                matched_query_terms=matched_terms,
                query_term_coverage=coverage,
            )
        )
    return results


def has_sufficient_evidence(question: str, retrieved: list[RetrievedChunk]) -> bool:
    query_terms = set(_tokens(question)) - QUERY_STOP_WORDS
    if not query_terms:
        return False

    required_matches = min(2, len(query_terms))
    return any(
        result.matched_query_terms >= required_matches
        and result.query_term_coverage >= MIN_QUERY_TERM_COVERAGE
        for result in retrieved
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]