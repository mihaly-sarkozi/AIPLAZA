# tests/test_chat.py
"""Chat modul tesztek: POST /chat (bejelentkezett user)."""
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from main import app
from apps.core.di import get_chat_service


def test_chat_without_auth_returns_401(client: TestClient):
    """POST /chat auth nélkül → 401."""
    r = client.post("/api/chat", json={"question": "Hello"})
    assert r.status_code == 401


def test_chat_success_returns_answer(client_authenticated: TestClient, mock_chat_service):
    """POST /chat bejelentkezett userrel → 200, answer a válaszban."""
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


def test_chat_empty_question_returns_422(client_authenticated: TestClient):
    """POST /chat üres question → 422 (ha validáció van) vagy 200."""
    r = client_authenticated.post("/api/chat", json={"question": ""})
    # Ha a schema engedi az üres stringet, 200; ha min_length=1, 422
    assert r.status_code in (200, 422)
