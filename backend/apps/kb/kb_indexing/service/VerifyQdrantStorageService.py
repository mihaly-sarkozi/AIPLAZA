from __future__ import annotations

import logging
from dataclasses import dataclass
from numbers import Real
from typing import Any

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.dto.IndexingVerificationDtos import QdrantVerificationResult
from apps.kb.kb_indexing.enums.IndexVerificationItemStatus import IndexVerificationItemStatus
from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.repository.IndexVerificationItemRepository import IndexVerificationItemRepository
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext, ProcessingFlowRecorder

logger = logging.getLogger(__name__)

_BATCH_SIZE = 64
_PROCESSING_MODULE = "kb_indexing"


@dataclass(frozen=True)
class _ChunkCheck:
    status: IndexVerificationItemStatus
    error_code: str | None
    error_message: str | None
    payload_found: bool
    vector_found: bool
    chunk_id_match: bool
    knowledge_base_id_match: bool
    training_item_id_match: bool
    vector_hash_match: bool
    payload_valid: bool


class VerifyQdrantStorageService:
    def __init__(
        self,
        qdrant_adapter: QdrantAdapter,
        indexed_chunk_repository: IndexedChunkRepository,
        verification_repository: IndexVerificationRepository,
        verification_item_repository: IndexVerificationItemRepository,
        *,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._qdrant = qdrant_adapter
        self._indexed_chunks = indexed_chunk_repository
        self._verifications = verification_repository
        self._verification_items = verification_item_repository
        self._flow_recorder = flow_recorder

    def verify(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        collection_name: str,
        flow_ctx: ProcessingFlowContext | None = None,
    ) -> QdrantVerificationResult:
        indexed_rows = [
            row
            for row in self._indexed_chunks.list_for_job(indexing_job_id)
            if row.status == IndexedChunkStatus.INDEXED.value
        ]
        verification = self._verifications.create(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            indexing_job_id=indexing_job_id,
            collection_name=collection_name,
            expected_points=len(indexed_rows),
        )
        self._record(flow_ctx, "QDRANT_VERIFICATION_STARTED", {"expected_points": len(indexed_rows)})

        if not indexed_rows:
            return self._finish_empty(verification.id, collection_name, flow_ctx)

        if not self._qdrant.collection_exists(collection_name):
            return self._finish_failed(
                verification,
                IndexVerificationStatus.FAILED,
                IndexingErrorCode.QDRANT_COLLECTION_NOT_FOUND.value,
                "Qdrant collection not found",
                collection_name,
                flow_ctx,
            )

        verified = 0
        missing = 0
        payload_mismatches = 0
        vector_hash_mismatches = 0
        failed = 0
        issue_codes: set[str] = set()
        item_rows = []

        for offset in range(0, len(indexed_rows), _BATCH_SIZE):
            batch = indexed_rows[offset : offset + _BATCH_SIZE]
            point_ids = [row.qdrant_point_id for row in batch]
            try:
                retrieved = self._qdrant.retrieve_points(
                    collection_name,
                    point_ids,
                    with_vectors=True,
                    with_payload=True,
                )
            except Exception as exc:
                logger.exception("Qdrant retrieve hiba")
                return self._finish_failed(
                    verification,
                    IndexVerificationStatus.FAILED,
                    IndexingErrorCode.QDRANT_RETRIEVE_FAILED.value,
                    str(exc),
                    collection_name,
                    flow_ctx,
                )

            retrieved_map = {str(item["id"]): item for item in retrieved}
            for row in batch:
                point = retrieved_map.get(str(row.qdrant_point_id))
                check = self._check_chunk_row(
                    row,
                    point,
                    knowledge_base_id=knowledge_base_id,
                    training_item_id=training_item_id,
                )
                if check.status == IndexVerificationItemStatus.VERIFIED:
                    verified += 1
                    self._record(flow_ctx, "QDRANT_POINT_VERIFIED", {"chunk_id": row.chunk_id})
                elif check.status == IndexVerificationItemStatus.MISSING_POINT:
                    missing += 1
                    issue_codes.add(check.error_code or IndexingErrorCode.QDRANT_POINT_MISSING.value)
                    self._record(flow_ctx, "QDRANT_POINT_MISSING", {"chunk_id": row.chunk_id})
                elif check.status == IndexVerificationItemStatus.VECTOR_MISMATCH:
                    vector_hash_mismatches += 1
                    issue_codes.add(check.error_code or IndexingErrorCode.QDRANT_VECTOR_HASH_MISMATCH.value)
                    self._record(flow_ctx, "QDRANT_VECTOR_HASH_MISMATCH", {"chunk_id": row.chunk_id})
                else:
                    payload_mismatches += 1
                    failed += 1
                    issue_codes.add(check.error_code or IndexingErrorCode.QDRANT_PAYLOAD_CHUNK_ID_MISMATCH.value)
                    self._record(flow_ctx, "QDRANT_PAYLOAD_MISMATCH", {"chunk_id": row.chunk_id})

                item_rows.append(
                    self._verification_items.build_item(
                        verification_id=verification.id,
                        tenant_slug=tenant_slug,
                        knowledge_base_id=knowledge_base_id,
                        training_item_id=training_item_id,
                        indexing_job_id=indexing_job_id,
                        indexed_chunk_id=row.id,
                        chunk_id=row.chunk_id,
                        embedding_id=row.embedding_id,
                        qdrant_collection=row.qdrant_collection,
                        qdrant_point_id=row.qdrant_point_id,
                        status=check.status.value,
                        error_code=check.error_code,
                        error_message=check.error_message,
                        payload_found=check.payload_found,
                        vector_found=check.vector_found,
                        chunk_id_match=check.chunk_id_match,
                        knowledge_base_id_match=check.knowledge_base_id_match,
                        training_item_id_match=check.training_item_id_match,
                        vector_hash_match=check.vector_hash_match,
                        payload_valid=check.payload_valid,
                    )
                )

        self._verification_items.add_items(item_rows)

        if verified == len(indexed_rows):
            status = IndexVerificationStatus.COMPLETED
            error_code = None
            error_message = None
            event_type = "QDRANT_VERIFICATION_COMPLETED"
        elif verified > 0:
            status = IndexVerificationStatus.PARTIAL
            error_code = IndexingErrorCode.QDRANT_VERIFICATION_PARTIAL.value
            error_message = f"verified={verified} expected={len(indexed_rows)}"
            event_type = "QDRANT_VERIFICATION_FAILED"
        else:
            status = IndexVerificationStatus.FAILED
            error_code = IndexingErrorCode.QDRANT_VERIFICATION_FAILED.value
            error_message = "No points verified in Qdrant"
            event_type = "QDRANT_VERIFICATION_FAILED"

        self._verifications.finish(
            verification.id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            verified_points=verified,
            missing_points=missing,
            payload_mismatches=payload_mismatches,
            vector_hash_mismatches=vector_hash_mismatches,
            failed_points=failed,
            metadata={"issue_codes": sorted(issue_codes)},
        )
        self._record(
            flow_ctx,
            event_type,
            {
                "verified_points": verified,
                "missing_points": missing,
                "payload_mismatches": payload_mismatches,
                "vector_hash_mismatches": vector_hash_mismatches,
            },
        )
        self._open_verification_issues(flow_ctx, issue_codes)

        return QdrantVerificationResult(
            verification_id=verification.id,
            status=status.value,
            error_code=error_code,
            error_message=error_message,
            collection_name=collection_name,
            expected_points=len(indexed_rows),
            verified_points=verified,
            missing_points=missing,
            payload_mismatches=payload_mismatches,
            vector_hash_mismatches=vector_hash_mismatches,
            failed_points=failed,
            issue_codes=tuple(sorted(issue_codes)),
        )

    def _check_chunk_row(
        self,
        row,
        point: dict[str, Any] | None,
        *,
        knowledge_base_id: str,
        training_item_id: str,
    ) -> _ChunkCheck:
        if point is None:
            return _ChunkCheck(
                status=IndexVerificationItemStatus.MISSING_POINT,
                error_code=IndexingErrorCode.QDRANT_POINT_MISSING.value,
                error_message="Point missing in Qdrant",
                payload_found=False,
                vector_found=False,
                chunk_id_match=False,
                knowledge_base_id_match=False,
                training_item_id_match=False,
                vector_hash_match=False,
                payload_valid=False,
            )

        payload = point.get("payload") or {}
        vector = point.get("vector")
        payload_found = bool(payload)
        vector_found = vector is not None and (
            isinstance(vector, list) and len(vector) > 0 if isinstance(vector, list) else True
        )

        if not payload_found:
            return _ChunkCheck(
                status=IndexVerificationItemStatus.PAYLOAD_MISMATCH,
                error_code=IndexingErrorCode.QDRANT_PAYLOAD_MISSING.value,
                error_message="Payload missing",
                payload_found=False,
                vector_found=vector_found,
                chunk_id_match=False,
                knowledge_base_id_match=False,
                training_item_id_match=False,
                vector_hash_match=False,
                payload_valid=False,
            )

        if not vector_found:
            return _ChunkCheck(
                status=IndexVerificationItemStatus.VECTOR_MISMATCH,
                error_code=IndexingErrorCode.QDRANT_VECTOR_MISSING.value,
                error_message="Vector missing",
                payload_found=True,
                vector_found=False,
                chunk_id_match=False,
                knowledge_base_id_match=False,
                training_item_id_match=False,
                vector_hash_match=False,
                payload_valid=False,
            )

        chunk_id_match = str(payload.get("chunk_id") or "") == row.chunk_id
        kb_match = str(payload.get("knowledge_base_id") or "") == knowledge_base_id
        item_match = str(payload.get("training_item_id") or "") == training_item_id
        payload_vector_hash = str(payload.get("vector_hash") or "")
        vector_hash_match = bool(row.vector_hash) and payload_vector_hash == row.vector_hash
        embedding_match = True
        if payload.get("embedding_id") is not None:
            embedding_match = str(payload.get("embedding_id") or "") == row.embedding_id

        language_ok = bool(str(payload.get("language_code") or "").strip())
        content_type_ok = bool(str(payload.get("content_type") or "").strip())
        score_ok = payload.get("overall_score") is None or isinstance(payload.get("overall_score"), Real)

        payload_valid = (
            chunk_id_match
            and kb_match
            and item_match
            and vector_hash_match
            and embedding_match
            and language_ok
            and content_type_ok
            and score_ok
        )

        if payload_valid:
            return _ChunkCheck(
                status=IndexVerificationItemStatus.VERIFIED,
                error_code=None,
                error_message=None,
                payload_found=True,
                vector_found=True,
                chunk_id_match=True,
                knowledge_base_id_match=True,
                training_item_id_match=True,
                vector_hash_match=True,
                payload_valid=True,
            )

        if not chunk_id_match:
            code = IndexingErrorCode.QDRANT_PAYLOAD_CHUNK_ID_MISMATCH.value
        elif not kb_match:
            code = IndexingErrorCode.QDRANT_PAYLOAD_KB_ID_MISMATCH.value
        elif not item_match:
            code = IndexingErrorCode.QDRANT_PAYLOAD_TRAINING_ITEM_ID_MISMATCH.value
        elif not vector_hash_match:
            code = IndexingErrorCode.QDRANT_VECTOR_HASH_MISMATCH.value
            return _ChunkCheck(
                status=IndexVerificationItemStatus.VECTOR_MISMATCH,
                error_code=code,
                error_message="Vector hash mismatch",
                payload_found=True,
                vector_found=True,
                chunk_id_match=chunk_id_match,
                knowledge_base_id_match=kb_match,
                training_item_id_match=item_match,
                vector_hash_match=False,
                payload_valid=False,
            )
        else:
            code = IndexingErrorCode.QDRANT_PAYLOAD_MISSING.value

        return _ChunkCheck(
            status=IndexVerificationItemStatus.PAYLOAD_MISMATCH,
            error_code=code,
            error_message="Payload validation failed",
            payload_found=True,
            vector_found=True,
            chunk_id_match=chunk_id_match,
            knowledge_base_id_match=kb_match,
            training_item_id_match=item_match,
            vector_hash_match=vector_hash_match,
            payload_valid=False,
        )

    def _finish_empty(
        self,
        verification_id: str,
        collection_name: str,
        flow_ctx: ProcessingFlowContext | None,
    ) -> QdrantVerificationResult:
        self._verifications.finish(
            verification_id,
            status=IndexVerificationStatus.FAILED,
            error_code=IndexingErrorCode.QDRANT_VERIFICATION_FAILED.value,
            error_message="No INDEXED chunks to verify",
        )
        self._record(flow_ctx, "QDRANT_VERIFICATION_FAILED", {"expected_points": 0})
        return QdrantVerificationResult(
            verification_id=verification_id,
            status=IndexVerificationStatus.FAILED.value,
            error_code=IndexingErrorCode.QDRANT_VERIFICATION_FAILED.value,
            error_message="No INDEXED chunks to verify",
            collection_name=collection_name,
            expected_points=0,
            verified_points=0,
            missing_points=0,
            payload_mismatches=0,
            vector_hash_mismatches=0,
            failed_points=0,
        )

    def _finish_failed(
        self,
        verification,
        status: IndexVerificationStatus,
        error_code: str,
        error_message: str,
        collection_name: str,
        flow_ctx: ProcessingFlowContext | None,
    ) -> QdrantVerificationResult:
        self._verifications.finish(
            verification.id,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )
        self._record(flow_ctx, "QDRANT_VERIFICATION_FAILED", {"error_code": error_code})
        self._open_verification_issues(flow_ctx, {error_code})
        return QdrantVerificationResult(
            verification_id=verification.id,
            status=status.value,
            error_code=error_code,
            error_message=error_message,
            collection_name=collection_name,
            expected_points=verification.expected_points,
            verified_points=0,
            missing_points=verification.expected_points,
            payload_mismatches=0,
            vector_hash_mismatches=0,
            failed_points=verification.expected_points,
            issue_codes=(error_code,),
        )

    def _record(self, flow_ctx: ProcessingFlowContext | None, event_type: str, summary: dict) -> None:
        if flow_ctx is None or self._flow_recorder is None:
            return
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="VERIFY_QDRANT",
            event_type=event_type,
            duration_ms=0,
            output_summary_json=summary,
        )

    def _open_verification_issues(self, flow_ctx: ProcessingFlowContext | None, codes: set[str]) -> None:
        if flow_ctx is None or self._flow_recorder is None or not codes:
            return
        for code in sorted(codes):
            self._flow_recorder.open_issue(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage="INDEXING",
                step="VERIFY_QDRANT",
                severity="error",
                issue_code=code,
            )


__all__ = ["VerifyQdrantStorageService"]
