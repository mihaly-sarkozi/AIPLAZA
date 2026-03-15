from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.domain.kb import KnowledgeBase

pytestmark = pytest.mark.integration


def test_delete_training_point_cascade_deletes_derived_and_qdrant():
    kb = KnowledgeBase(
        id=3,
        uuid="kb-3",
        name="KB-3",
        description="",
        qdrant_collection_name="kb_kb-3",
        created_at=None,
        updated_at=None,
    )
    repo = MagicMock()
    repo.get_by_uuid.return_value = kb
    repo.delete_derived_records_by_source_point_id.return_value = 9
    repo.delete_training_log_by_point_id.return_value = True

    qdrant = MagicMock()
    qdrant.delete_points_by_source_point_id = AsyncMock(return_value=None)

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    asyncio.run(svc.delete_training_point("kb-3", "point-1"))

    repo.delete_derived_records_by_source_point_id.assert_called_once_with(3, "point-1")
    qdrant.delete_points_by_source_point_id.assert_awaited_once_with("kb_kb-3", "point-1")
    repo.delete_training_log_by_point_id.assert_called_once_with(3, "point-1")


def test_delete_training_point_queues_outbox_when_qdrant_delete_fails():
    kb = KnowledgeBase(
        id=3,
        uuid="kb-3",
        name="KB-3",
        description="",
        qdrant_collection_name="kb_kb-3",
        created_at=None,
        updated_at=None,
    )
    repo = MagicMock()
    repo.get_by_uuid.return_value = kb
    repo.delete_derived_records_by_source_point_id.return_value = 5
    repo.delete_training_log_by_point_id.return_value = True
    qdrant = MagicMock()
    qdrant.delete_points_by_source_point_id = AsyncMock(side_effect=RuntimeError("qdrant timeout"))

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    asyncio.run(svc.delete_training_point("kb-3", "point-1"))

    repo.enqueue_vector_outbox.assert_called_once()
    repo.delete_training_log_by_point_id.assert_called_once_with(3, "point-1")
