from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_kb_service():
    return MagicMock()


def test_reindex_kb_endpoint_calls_service(client_authenticated: TestClient, mock_kb_service, app):
    from apps.core.di import get_kb_service

    mock_kb_service.user_can_train.return_value = True
    mock_kb_service.reindex_kb = AsyncMock(return_value={"status": "ok", "reindexed": 2})
    app.dependency_overrides[get_kb_service] = lambda: mock_kb_service
    try:
        r = client_authenticated.post("/api/kb/kb-123/reindex")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        mock_kb_service.reindex_kb.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_kb_service, None)


def test_reindex_training_point_endpoint_calls_service(client_authenticated: TestClient, mock_kb_service, app):
    from apps.core.di import get_kb_service

    mock_kb_service.user_can_train.return_value = True
    mock_kb_service.reindex_training_point = AsyncMock(return_value={"status": "ok"})
    app.dependency_overrides[get_kb_service] = lambda: mock_kb_service
    try:
        r = client_authenticated.post("/api/kb/kb-123/train/points/p-1/reindex")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        mock_kb_service.reindex_training_point.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_kb_service, None)


def test_training_point_source_endpoint_calls_service_and_returns_source(client_authenticated: TestClient, mock_kb_service, app):
    from apps.core.di import get_kb_service

    mock_kb_service.user_can_use.return_value = True
    mock_kb_service.get_training_point_source.return_value = {
        "kb_uuid": "kb-123",
        "point_id": "p-1",
        "title": "Forrás",
        "content": "Sanitized tartalom",
        "created_at": None,
    }
    app.dependency_overrides[get_kb_service] = lambda: mock_kb_service
    try:
        r = client_authenticated.get("/api/kb/kb-123/train/points/p-1/source")
        assert r.status_code == 200
        data = r.json()
        assert data["point_id"] == "p-1"
        assert data["content"] == "Sanitized tartalom"
        mock_kb_service.get_training_point_source.assert_called_once_with("kb-123", "p-1")
    finally:
        app.dependency_overrides.pop(get_kb_service, None)


def test_outbox_stats_endpoint_calls_service(client_authenticated: TestClient, mock_kb_service, app):
    from apps.core.di import get_kb_service

    mock_kb_service.get_vector_outbox_stats.return_value = {
        "kb_uuid": "kb-123",
        "total": 4,
        "by_status": {"pending": 2, "failed": 2},
        "by_operation": {"reindex_training_point": 3, "delete_source_point": 1},
        "max_attempts": 5,
        "oldest_due_at": None,
        "recent_items": [],
    }
    app.dependency_overrides[get_kb_service] = lambda: mock_kb_service
    try:
        r = client_authenticated.get("/api/kb/outbox/stats?kb_uuid=kb-123&recent_limit=10")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4
        assert data["by_status"]["failed"] == 2
        mock_kb_service.get_vector_outbox_stats.assert_called_once_with(kb_uuid="kb-123", recent_limit=10)
    finally:
        app.dependency_overrides.pop(get_kb_service, None)
