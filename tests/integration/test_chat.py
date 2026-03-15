# tests/integration/test_chat.py
"""Chat modul tesztek: POST /chat (bejelentkezett user)."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_chat_without_auth_returns_401(client: TestClient):
    """POST /chat auth nélkül → 401."""
    r = client.post("/api/chat", json={"question": "Hello"})
    assert r.status_code == 401


def test_chat_success_returns_answer(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat bejelentkezett userrel → 200, answer a válaszban."""
    from apps.core.di import get_chat_service
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
    from apps.core.di import get_chat_service

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
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post("/api/chat", json={"question": "Mi újság?"})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "A válasz"
        assert len(data.get("sources") or []) == 1
        assert data["sources"][0]["point_id"] == "p-1"
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_debug_false_omits_debug_field(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat debug nélkül maradjon backward compatible."""
    from apps.core.di import get_chat_service

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


def test_chat_debug_true_returns_debug_payload(client_authenticated: TestClient, mock_chat_service, app):
    """POST /chat debug=true esetén a debug payload visszajön a válaszban."""
    from apps.core.di import get_chat_service

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
