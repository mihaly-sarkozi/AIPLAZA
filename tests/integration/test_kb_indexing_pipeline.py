from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.infrastructure.db.models import PERSONAL_DATA_MODE_DISABLED

pytestmark = pytest.mark.integration


def _kb() -> KnowledgeBase:
    return KnowledgeBase(
        id=10,
        uuid="kb-uuid-1",
        name="KB",
        description=None,
        qdrant_collection_name="kb_kb-uuid-1",
        personal_data_mode=PERSONAL_DATA_MODE_DISABLED,
        created_at=None,
        updated_at=None,
    )


def test_add_block_runs_indexing_pipeline_after_training_log():
    repo = MagicMock()
    repo.get_by_uuid.return_value = _kb()
    repo.get_training_log_by_idempotency_key.return_value = None
    repo.add_training_log.return_value = None
    qdrant = MagicMock()
    pipeline = MagicMock()
    pipeline.index_training_content = AsyncMock(return_value={"sentence_count": 2, "chunk_count": 1})

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=pipeline)
    out = asyncio.run(
        svc.add_block(
            uuid="kb-uuid-1",
            title="Teszt",
            content="Ez egy sanitized tartalom.",
            current_user_id=7,
        )
    )

    assert out["status"] == "ok"
    assert out["indexing"]["sentence_count"] == 2
    repo.add_training_log.assert_called_once()
    pipeline.index_training_content.assert_awaited_once()


def test_add_block_idempotency_key_replays_without_reindex():
    repo = MagicMock()
    repo.get_by_uuid.return_value = _kb()
    repo.get_training_log_by_idempotency_key.return_value = {
        "point_id": "existing-point-1",
        "title": "Korabbi",
        "content": "Mar mentve",
    }
    qdrant = MagicMock()
    pipeline = MagicMock()
    pipeline.index_training_content = AsyncMock()

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=pipeline)
    out = asyncio.run(
        svc.add_block(
            uuid="kb-uuid-1",
            title="Teszt",
            content="Ugyanaz a tartalom.",
            idempotency_key="idem-1",
            current_user_id=7,
        )
    )

    assert out["status"] == "ok"
    assert out["idempotent_replay"] is True
    assert out["point_id"] == "existing-point-1"
    repo.add_training_log.assert_not_called()
    pipeline.index_training_content.assert_not_awaited()


def test_add_block_queues_outbox_when_indexing_fails():
    repo = MagicMock()
    repo.get_by_uuid.return_value = _kb()
    repo.get_training_log_by_idempotency_key.return_value = None
    repo.add_training_log.return_value = None
    qdrant = MagicMock()
    pipeline = MagicMock()
    pipeline.index_training_content = AsyncMock(side_effect=RuntimeError("qdrant down"))

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=pipeline)
    out = asyncio.run(
        svc.add_block(
            uuid="kb-uuid-1",
            title="Teszt",
            content="Sanitized tartalom.",
            current_user_id=7,
        )
    )

    assert out["status"] == "ok"
    assert out["indexing"]["queued_for_retry"] is True
    repo.enqueue_vector_outbox.assert_called_once()

