# tests/integration/test_chat.py
"""Chat modul tesztek: POST /chat (bejelentkezett user)."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from tests.conftest import get_app
from apps.core.di import get_chat_service

pytestmark = pytest.mark.integration


def test_chat_without_auth_returns_401(client: TestClient):
    """POST /chat auth nélkül → 401."""
    r = client.post("/api/chat", json={"question": "Hello"})
    assert r.status_code == 401


def test_chat_success_returns_answer(client_authenticated: TestClient, mock_chat_service):
    """POST /chat bejelentkezett userrel → 200, answer a válaszban."""
    app = get_app()
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


@pytest.mark.integration
def test_chat_empty_question_rejected(client_authenticated: TestClient):
    """POST /chat üres question → 422 (validáció) vagy 200; soha 500. Prefer 422."""
    r = client_authenticated.post("/api/chat", json={"question": ""})
    assert r.status_code in (200, 422), f"Unexpected {r.status_code}: {r.text[:200]}"
    if r.status_code == 422:
        assert "question" in r.json().get("detail", [{}])[0].get("loc", [])
    elif r.status_code == 200:
        # If API accepts empty, response should not be a server error
        assert "detail" not in r.json() or "error" not in str(r.json().get("detail", "")).lower()
