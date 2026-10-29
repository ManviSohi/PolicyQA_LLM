import json
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.config import settings
from app.models import Chunk, Citation, Conversation, Document, Message
from app.rag.retrieval import has_sufficient_evidence, retrieve_document_chunks
from app.rag.qa import SYSTEM_PROMPT


def test_ask_uses_only_selected_document_and_persists_grounded_exchange(
    client: TestClient, monkeypatch, pdf_factory
) -> None:
    document_a_text = "Employees may work remotely from another state only with prior written approval from Human Resources."
    document_b_text = "Employees may work remotely from another state without approval in this policy."
    document_a = upload_pdf(client, "policy-a.pdf", pdf_factory(document_a_text))
    document_b = upload_pdf(client, "policy-b.pdf", pdf_factory(document_b_text))
    sent_payloads: list[dict] = []

    def fake_groq(api_key: str):
        assert api_key == "test-only-key"

        def complete(**kwargs):
            sent_payloads.append(kwargs)
            messages = kwargs["messages"]
            assert "answer ONLY from supplied evidence" in messages[0]["content"]
            assert "do not use outside knowledge" in messages[0]["content"]
            evidence_text = messages[1]["content"].split("Supplied evidence (JSON data):\n", 1)[1]
            evidence = json.loads(evidence_text)
            assert evidence
            assert all(document_b_text not in item["text"] for item in evidence)
            structured = {
                "answer": "Prior written approval from Human Resources is required.",
                "used": [evidence[0]["chunk_id"]],
                "grounded": True,
                "needs_clarification": False,
            }
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(structured)))]
            )

        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=complete))
        )

    monkeypatch.setattr(settings, "groq_api_key", "test-only-key")
    monkeypatch.setattr("app.rag.qa.Groq", fake_groq)
    response = client.post(
        "/api/ask",
        json={"document_id": document_a["id"], "question": "Can employees work remotely from another state?"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["document_id"] == document_a["id"]
    assert result["grounded"] is True
    assert result["latency_ms"] >= 0
    assert len(result["citations"]) == 1
    citation = result["citations"][0]
    assert citation["chunk_id"] in {chunk["id"] for chunk in client.get(f"/api/documents/{document_a['id']}").json()["chunks"]}
    assert citation["chunk_id"] not in {chunk["id"] for chunk in client.get(f"/api/documents/{document_b['id']}").json()["chunks"]}
    assert "prior written approval" in citation["quote"].lower()
    assert 0 <= citation["relevance_score"] <= 1
    assert len(sent_payloads) == 1

    with database.SessionLocal() as session:
        conversation = session.get(Conversation, UUID(result["conversation_id"]))
        assert conversation is not None
        assert str(conversation.document_id) == document_a["id"]
        messages = list(
            session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at, Message.role)
            )
        )
        assert {message.role for message in messages} == {"user", "assistant"}
        assistant = next(message for message in messages if message.role == "assistant")
        assert assistant.latency_ms == result["latency_ms"]
        stored_citations = list(session.scalars(select(Citation).where(Citation.message_id == assistant.id)))
        assert len(stored_citations) == 1
        assert stored_citations[0].relevance_score == citation["relevance_score"]


def test_ask_abstains_without_evidence_and_does_not_call_groq(
    client: TestClient, monkeypatch, pdf_factory
) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory("Employees may request annual leave through their manager."),
    )

    def unexpected_groq_call(*args, **kwargs):
        raise AssertionError("Groq must not be called without useful evidence")

    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr("app.rag.qa.Groq", unexpected_groq_call)
    response = client.post(
        "/api/ask",
        json={"document_id": document["id"], "question": "What is the lunar taxonomy schedule?"},
    )

    assert response.status_code == 200
    assert response.json()["grounded"] is False
    assert response.json()["citations"] == []
    assert "does not provide enough information" in response.json()["answer"]


def test_ask_validates_empty_question_and_document_status(
    client: TestClient, pdf_factory
) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory("Employees may request annual leave through their manager."),
    )
    empty = client.post(
        "/api/ask",
        json={"document_id": document["id"], "question": "   "},
    )
    assert empty.status_code == 400

    missing = client.post(
        "/api/ask",
        json={"document_id": "00000000-0000-0000-0000-000000000001", "question": "leave"},
    )
    assert missing.status_code == 404


def test_ask_returns_sanitized_groq_errors(client: TestClient, monkeypatch, pdf_factory, caplog) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory("Employees may request annual leave through their manager."),
    )
    payload = {"document_id": document["id"], "question": "How may employees request annual leave?"}
    monkeypatch.setattr(settings, "groq_api_key", "")
    unavailable = client.post("/api/ask", json=payload)
    assert unavailable.status_code == 503

    secret_marker = "test-only-secret-marker"
    monkeypatch.setattr(settings, "groq_api_key", secret_marker)

    def failing_groq(api_key: str):
        assert api_key == secret_marker
        raise RuntimeError(f"provider rejected key {secret_marker}")

    monkeypatch.setattr("app.rag.qa.Groq", failing_groq)
    failed = client.post("/api/ask", json=payload)
    assert failed.status_code == 502
    assert secret_marker not in failed.text
    assert secret_marker not in caplog.text


def test_ask_rejects_chunk_ids_not_returned_by_retrieval(
    client: TestClient, monkeypatch, pdf_factory
) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory("Employees may request annual leave through their manager."),
    )
    monkeypatch.setattr(settings, "groq_api_key", "test-only-key")

    def fake_groq(api_key: str):
        def complete(**kwargs):
            response = {
                "answer": "Unsupported citation test.",
                "used": [str(uuid4())],
                "grounded": True,
                "needs_clarification": False,
            }
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(response)))]
            )

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))

    monkeypatch.setattr("app.rag.qa.Groq", fake_groq)
    response = client.post(
        "/api/ask",
        json={"document_id": document["id"], "question": "How may employees request annual leave?"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "The answer service returned an invalid response."


def test_ask_accepts_markdown_fenced_json_from_groq(
    client: TestClient, monkeypatch, pdf_factory
) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory("Employees may request annual leave through their manager."),
    )
    monkeypatch.setattr(settings, "groq_api_key", "test-only-key")

    def fake_groq(api_key: str):
        def complete(**kwargs):
            response = {
                "answer": "Employees may request annual leave through their manager.",
                "used": [],
                "grounded": False,
                "needs_clarification": False,
            }
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=f"```json\n{json.dumps(response)}\n```")
                    )
                ]
            )

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))

    monkeypatch.setattr("app.rag.qa.Groq", fake_groq)
    response = client.post(
        "/api/ask",
        json={"document_id": document["id"], "question": "What is the lunar taxonomy schedule?"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["grounded"] is False
    assert "does not provide enough information" in response.json()["answer"]


def test_bm25_keeps_term_matches_with_negative_small_corpus_idf(client: TestClient) -> None:
    with database.SessionLocal() as session:
        document = Document(
            filename="single-chunk.pdf",
            file_type="pdf",
            file_size=1,
            sha256="a" * 64,
            status="indexed",
        )
        session.add(document)
        session.flush()
        session.add(
            Chunk(
                document_id=document.id,
                chunk_index=0,
                text="a",
                page=1,
                section=None,
                token_count=1,
                content_hash="b" * 64,
            )
        )
        session.commit()

        results = retrieve_document_chunks(session, document.id, "a")

    assert len(results) == 1
    assert results[0].chunk.text == "a"


def test_leave_policy_evidence_gate_accepts_paraphrase_and_rejects_unknown(
    client: TestClient, pdf_factory
) -> None:
    document = upload_pdf(
        client,
        "leave-policy.pdf",
        pdf_factory(
            "Employees may be eligible for annual paid leave, sick leave, parental leave, "
            "and bereavement leave. Medical documentation may be required for absences "
            "beyond a defined threshold."
        ),
    )

    with database.SessionLocal() as session:
        answerable = retrieve_document_chunks(
            session, UUID(document["id"]), "What types of leave are available?"
        )
        exception = retrieve_document_chunks(
            session, UUID(document["id"]), "When may medical documentation be required?"
        )
        unknown = retrieve_document_chunks(
            session, UUID(document["id"]), "Does this policy reimburse international sabbatical travel?"
        )

    assert any("annual paid leave" in item.chunk.text for item in answerable)
    assert has_sufficient_evidence("What types of leave are available?", answerable)
    assert has_sufficient_evidence("When may medical documentation be required?", exception)
    assert not has_sufficient_evidence(
        "Does this policy reimburse international sabbatical travel?", unknown
    )


def upload_pdf(client: TestClient, filename: str, content: bytes) -> dict:
    response = client.post(
        "/api/documents",
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()