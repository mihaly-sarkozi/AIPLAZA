from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.knowledge.application.knowledge_service import KnowledgeBaseService

pytestmark = pytest.mark.unit


def test_process_vector_outbox_handles_delete_operation():
    repo = MagicMock()
    repo.list_due_vector_outbox.return_value = [
        {
            "id": 1,
            "operation_type": "delete_source_point",
            "payload": {"collection_name": "kb_col", "source_point_id": "p-1"},
            "attempts": 0,
        }
    ]
    qdrant = MagicMock()
    qdrant.delete_points_by_source_point_id = AsyncMock(return_value=None)
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)

    out = asyncio.run(svc.process_vector_outbox(limit=20))
    assert out["processed"] == 1
    assert out["done"] == 1
    repo.mark_vector_outbox_done.assert_called_once_with(1)


def test_process_vector_outbox_marks_retry_on_failure():
    repo = MagicMock()
    repo.list_due_vector_outbox.return_value = [
        {
            "id": 2,
            "operation_type": "delete_source_point",
            "payload": {"collection_name": "kb_col", "source_point_id": "p-2"},
            "attempts": 1,
        }
    ]
    qdrant = MagicMock()
    qdrant.delete_points_by_source_point_id = AsyncMock(side_effect=RuntimeError("timeout"))
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)

    out = asyncio.run(svc.process_vector_outbox(limit=20))
    assert out["processed"] == 1
    assert out["failed"] == 1
    assert len(out["failed_items"]) == 1
    assert out["failed_items"][0]["outbox_id"] == 2
    repo.mark_vector_outbox_retry.assert_called_once()


def test_process_vector_outbox_skips_when_table_missing():
    repo = MagicMock()
    repo.list_due_vector_outbox.side_effect = RuntimeError(
        'relation "kb_vector_outbox" does not exist'
    )
    qdrant = MagicMock()
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)

    out = asyncio.run(svc.process_vector_outbox(limit=20))

    assert out["processed"] == 0
    assert out["done"] == 0
    assert out["failed"] == 0
    assert out["skipped"] == "missing_kb_vector_outbox_table"
    repo.mark_vector_outbox_done.assert_not_called()
    repo.mark_vector_outbox_retry.assert_not_called()
