from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.dto.QdrantDeleteResult import QdrantDeleteResult
from apps.kb.kb_indexing.service.DeleteIndexedChunksService import DeleteIndexedChunksService
from apps.kb.kb_indexing.service.StartIndexingService import StartIndexingService


def test_start_indexing_creates_failed_job_when_embedding_missing():
    job_repo = MagicMock()
    job_repo.get_active_job_id_for_embedding.return_value = None
    job_repo.create_job.return_value = SimpleNamespace(id="idx_job_1")

    kb_reader = MagicMock()
    kb_reader.exists.return_value = True

    failure_recorder = MagicMock()
    failure_recorder.create_failed_job.return_value = SimpleNamespace(id="idx_job_failed")

    service = StartIndexingService(
        job_repo,
        SimpleNamespace(get_job=lambda _: None),
        kb_reader,
        MagicMock(),
        failure_recorder,
    )

    status = service.start(
        tenant_slug="tenant",
        knowledge_base_id="kb_1",
        training_item_id="item_1",
        understanding_job_id="u_1",
        discovery_job_id="d_1",
        embedding_job_id="emb_missing",
        created_by=1,
    )

    assert status == IndexingStatus.FAILED
    failure_recorder.create_failed_job.assert_called_once()
    assert failure_recorder.create_failed_job.call_args.kwargs["error_code"] == IndexingErrorCode.EMBEDDING_JOB_NOT_FOUND.value


def test_delete_indexed_chunks_marks_replaced():
    row = SimpleNamespace(
        id="chunk_row_1",
        chunk_id="c1",
        qdrant_point_id="p1",
        qdrant_collection="kb_test",
        embedding_id="e1",
        payload_hash="ph",
        vector_hash="vh",
        training_item_id="item_1",
        indexing_job_id="job_1",
    )
    indexed_repo = MagicMock()
    indexed_repo.list_indexed_for_training_item.return_value = [row]
    qdrant = MagicMock()
    qdrant.delete_points.return_value = QdrantDeleteResult(requested=1, deleted=1)

    service = DeleteIndexedChunksService(qdrant, indexed_repo)
    result = service.delete_for_training_item(
        tenant_slug="tenant",
        knowledge_base_id="kb_1",
        training_item_id="item_1",
        collection_name="kb_test",
        new_status=IndexedChunkStatus.REPLACED.value,
    )

    assert result.postgres_updated == 1
    indexed_repo.update_chunk_status.assert_called_once()
    assert indexed_repo.update_chunk_status.call_args.kwargs["status"] == IndexedChunkStatus.REPLACED.value
