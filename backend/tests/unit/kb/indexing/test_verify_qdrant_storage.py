from __future__ import annotations

from types import SimpleNamespace

from apps.kb.kb_indexing.enums.IndexVerificationItemStatus import IndexVerificationItemStatus
from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.dto.IndexingVerificationDtos import QdrantVerificationResult
from apps.kb.kb_indexing.service.MarkReadyForSearchService import MarkReadyForSearchService
from apps.kb.kb_indexing.service.VerifyQdrantStorageService import VerifyQdrantStorageService


def _verify_service() -> VerifyQdrantStorageService:
    return VerifyQdrantStorageService(None, None, None, None)


def test_check_chunk_row_verified():
    row = SimpleNamespace(chunk_id="chunk_1", vector_hash="abc", embedding_id="emb_1")
    point = {
        "payload": {
            "chunk_id": "chunk_1",
            "knowledge_base_id": "kb_1",
            "training_item_id": "item_1",
            "vector_hash": "abc",
            "embedding_id": "emb_1",
            "language_code": "hu",
            "content_type": "text",
            "overall_score": 0.8,
        },
        "vector": [0.1, 0.2],
    }
    check = _verify_service()._check_chunk_row(row, point, knowledge_base_id="kb_1", training_item_id="item_1")
    assert check.status == IndexVerificationItemStatus.VERIFIED
    assert check.payload_valid is True


def test_check_chunk_row_missing_point():
    row = SimpleNamespace(chunk_id="chunk_1", vector_hash="abc", embedding_id="emb_1")
    check = _verify_service()._check_chunk_row(row, None, knowledge_base_id="kb_1", training_item_id="item_1")
    assert check.status == IndexVerificationItemStatus.MISSING_POINT
    assert check.error_code == IndexingErrorCode.QDRANT_POINT_MISSING.value


def test_check_chunk_row_vector_hash_mismatch():
    row = SimpleNamespace(chunk_id="chunk_1", vector_hash="abc", embedding_id="emb_1")
    point = {
        "payload": {
            "chunk_id": "chunk_1",
            "knowledge_base_id": "kb_1",
            "training_item_id": "item_1",
            "vector_hash": "wrong",
            "embedding_id": "emb_1",
            "language_code": "hu",
            "content_type": "text",
        },
        "vector": [0.1],
    }
    check = _verify_service()._check_chunk_row(row, point, knowledge_base_id="kb_1", training_item_id="item_1")
    assert check.status == IndexVerificationItemStatus.VECTOR_MISMATCH
    assert check.error_code == IndexingErrorCode.QDRANT_VECTOR_HASH_MISMATCH.value


def test_mark_ready_accepts_pipeline_status_before_persist():
    verification = QdrantVerificationResult(
        verification_id="ver_1",
        status=IndexVerificationStatus.COMPLETED.value,
        error_code=None,
        error_message=None,
        collection_name="kb_test",
        expected_points=10,
        verified_points=10,
        missing_points=0,
        payload_mismatches=0,
        vector_hash_mismatches=0,
        failed_points=0,
    )
    service = MarkReadyForSearchService(
        SimpleNamespace(get_job=lambda _: SimpleNamespace(status=IndexingStatus.RUNNING.value)),
        SimpleNamespace(get_job=lambda _: {"status": "COMPLETED", "chunks_embedded": 10}),
        SimpleNamespace(get_for_knowledge_base=lambda _: None, upsert=lambda _: None),
    )
    result = service.mark_if_ready(
        tenant_slug="tenant",
        knowledge_base_id="kb_1",
        training_item_id="item_1",
        indexing_job_id="job_1",
        embedding_job_id="emb_job_1",
        verification=verification,
        indexing_status=IndexingStatus.COMPLETED,
    )
    assert result.ready_for_search is True
    assert result.qdrant_verified is True
