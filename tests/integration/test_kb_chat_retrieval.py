from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_chat_accepts_optional_kb_uuid_and_debug(client_authenticated: TestClient, mock_chat_service, app):
    from apps.core.di import get_chat_service

    async def _chat(question: str, user_id=None, user_role=None, kb_uuid=None, debug=False):
        assert question == "Mikor volt tréning?"
        assert kb_uuid == "kb-123"
        assert debug is True
        return "OK"

    mock_chat_service.chat = AsyncMock(side_effect=_chat)
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post(
            "/api/chat",
            json={"question": "Mikor volt tréning?", "kb_uuid": "kb-123", "debug": True},
        )
        assert r.status_code == 200
        assert r.json()["answer"] == "OK"
    finally:
        app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_403_when_service_denies_kb_scope(client_authenticated: TestClient, mock_chat_service, app):
    from apps.core.di import get_chat_service

    async def _chat(question: str, user_id=None, user_role=None, kb_uuid=None, debug=False):
        raise PermissionError("denied")

    mock_chat_service.chat = AsyncMock(side_effect=_chat)
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        r = client_authenticated.post(
            "/api/chat",
            json={"question": "Teszt?", "kb_uuid": "kb-123"},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
