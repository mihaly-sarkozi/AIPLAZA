"""Chat modul tesztek: POST /chat (bejelentkezett user)."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("allow_chat_usage")]


def test_chat_without_auth_returns_401(client: TestClient):
    """POST /chat auth nélkül → 401."""
    r = client.post("/api/chat", json={"question": "Hello"})
    assert r.status_code == 401


def test_chat_success_returns_answer(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat bejelentkezett userrel → 200, answer a válaszban."""
    from apps.chat.dependencies import get_chat_service
    async def _chat(question: str):
        return f"Válasz: {question}"
    mock_chat_service.chat = AsyncMock(side_effect=_chat)
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Mi a főváros?"})
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        assert "Mi a főváros?" in data["answer"] or "Válasz" in data["answer"]
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_sources_when_available(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat visszaad forrásokat, ha a service támogatja."""
    from apps.chat.dependencies import get_chat_service

    mock_chat_service.chat_with_sources = AsyncMock(
        return_value={
            "answer": "A válasz",
            "query_run_id": "qr-1",
            "answer_mode": "direct",
            "answer_source": "knowledge",
            "confidence": 0.9,
            "evidence": [{"claim_id": "c-1", "sentence_id": "s-1", "source_id": "src-1"}],
            "cited_claim_ids": ["c-1"],
            "cited_sentence_ids": ["s-1"],
            "cited_source_ids": ["src-1"],
            "query_profile": {"intent": "state"},
            "matched_chunks": [{"profile_id": "profile-1"}],
            "claims": [{"claim_id": "c-1"}],
            "sources": [
                {
                    "kb_uuid": "kb-1",
                    "point_id": "p-1",
                    "source_id": "src-1",
                    "title": "Dokumentum 1",
                    "snippet": "Részlet",
                    "source_type": "text",
                }
            ],
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Mi újság?"})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "A válasz"
        assert data["query_run_id"] == "qr-1"
        assert data["answer_mode"] == "direct"
        assert data["answer_source"] == "knowledge"
        assert data["confidence"] == 0.9
        assert data["evidence"][0]["claim_id"] == "c-1"
        assert data["query_profile"] == {"intent": "state"}
        assert data["matched_chunks"][0]["profile_id"] == "profile-1"
        assert data["claims"][0]["claim_id"] == "c-1"
        assert len(data.get("sources") or []) == 1
        assert data["sources"][0]["point_id"] == "p-1"
        assert data["sources"][0]["source_id"] == "src-1"
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_debug_false_omits_debug_field(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat debug nélkül maradjon backward compatible."""
    from apps.chat.dependencies import get_chat_service

    mock_chat_service.chat_with_sources = AsyncMock(
        return_value={
            "answer": "A válasz",
            "sources": [],
            "debug": {
                "top_assertion_count": 2,
                "evidence_sentence_count": 1,
                "source_chunk_count": 1,
            },
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Mi újság?"})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "A válasz"
        assert "debug" not in data
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_source_download_returns_query_context_attachment(client_authenticated: TestClient, mock_chat_service, app):
    from apps.chat.dependencies import get_chat_service

    mock_chat_service.download_answer_source.return_value = {
        "filename": "aiplaza-context-src-1.txt",
        "content_type": "text/plain; charset=utf-8",
        "body": b"Question: Mi ujsag?\nContext: reszlet",
        "corpus_uuid": "kb-1",
    }
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.get("/api/chat/sources/qr-1/src-1/download")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        assert "filename*=UTF-8''aiplaza-context-src-1.txt" in r.headers["content-disposition"]
        assert b"Context: reszlet" in r.content
        mock_chat_service.download_answer_source.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_debug_true_returns_debug_payload(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat debug=true esetén a debug payload visszajön a válaszban."""
    from apps.chat.dependencies import get_chat_service

    mock_chat_service.chat_with_sources = AsyncMock(
        return_value={
            "answer": "A válasz",
            "sources": [
                {
                    "kb_uuid": "kb-1",
                    "point_id": "p-1",
                    "title": "Dokumentum 1",
                    "snippet": "Részlet",
                }
            ],
            "debug": {
                "query_focus": {"intent": "summary"},
                "scoring_summary": {"retrieval_mode": "assertion_first"},
                "top_assertion_count": 2,
                "evidence_sentence_count": 1,
                "source_chunk_count": 1,
                "related_entity_count": 1,
                "context_preview": "Primary assertions: ...",
                "top_assertion_ids": ["assertion-1", "assertion-2"],
                "source_point_ids": ["p-1"],
            },
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Mi újság?", "debug": True})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "A válasz"
        assert "debug" in data
        assert data["debug"]["top_assertion_count"] == 2
        assert data["debug"]["evidence_sentence_count"] == 1
        assert data["debug"]["source_chunk_count"] == 1
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_insufficient_information_when_no_context(client_authenticated: TestClient, mock_chat_service, app):
    """Ha nincs használható context, a válasz ne menjen LLM-only irányba."""
    from apps.chat.dependencies import get_chat_service

    mock_chat_service.chat_with_sources = AsyncMock(
        return_value={
            "answer": "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján.",
            "sources": [],
            "debug": {
                "top_assertion_count": 0,
                "evidence_sentence_count": 0,
                "source_chunk_count": 0,
                "context_preview": "",
            },
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Ismeretlen kérdés?", "debug": True})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján."
        assert data["sources"] == []
        assert data["debug"]["top_assertion_count"] == 0
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


@pytest.mark.integration
@pytest.mark.release_acceptance
def test_chat_empty_question_returns_422(client_authenticated: TestClient):
    """POST /chat with empty question → 422 (validation error)."""
    r = client_authenticated.post("/api/chat", json={"question": ""})
    assert r.status_code == 422, f"Expected 422 for empty question, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", [])
    assert isinstance(detail, list) and len(detail) >= 1
    loc = detail[0].get("loc", [])
    assert "question" in loc
