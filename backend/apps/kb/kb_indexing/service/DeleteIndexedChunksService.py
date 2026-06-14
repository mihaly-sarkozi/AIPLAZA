from __future__ import annotations

import logging
from collections import defaultdict

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.dto.DeleteIndexedChunksResult import DeleteIndexedChunksResult
from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
from shared.utils.clock import utc_now_naive

logger = logging.getLogger(__name__)

_INDEXED = IndexedChunkStatus.INDEXED.value
_REMOVED = IndexedChunkStatus.REMOVED.value
_REPLACED = IndexedChunkStatus.REPLACED.value
_DELETE_FAILED = IndexedChunkStatus.DELETE_FAILED.value


class DeleteIndexedChunksService:
    """Qdrant point törlés + Postgres soft-state frissítés."""

    def __init__(
        self,
        qdrant_adapter: QdrantAdapter,
        indexed_chunk_repository: IndexedChunkRepository,
    ) -> None:
        self._qdrant = qdrant_adapter
        self._indexed_chunks = indexed_chunk_repository

    def delete_for_training_item(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        collection_name: str,
        removed_by: int | None = None,
        reason: str | None = None,
        new_status: str = _REMOVED,
    ) -> DeleteIndexedChunksResult:
        rows = self._indexed_chunks.list_indexed_for_training_item(
            training_item_id,
            knowledge_base_id=knowledge_base_id,
        )
        return self._delete_rows(
            rows,
            collection_name=collection_name,
            removed_by=removed_by,
            reason=reason,
            new_status=new_status,
        )

    def delete_for_knowledge_base(
        self,
        *,
        knowledge_base_id: str,
        collection_name: str,
        removed_by: int | None = None,
        reason: str | None = None,
    ) -> DeleteIndexedChunksResult:
        rows = self._indexed_chunks.list_indexed_for_knowledge_base(knowledge_base_id)
        return self._delete_rows(
            rows,
            collection_name=collection_name,
            removed_by=removed_by,
            reason=reason,
            new_status=_REMOVED,
        )

    def delete_for_indexing_job(
        self,
        *,
        indexing_job_id: str,
        collection_name: str,
        removed_by: int | None = None,
        reason: str | None = None,
    ) -> DeleteIndexedChunksResult:
        rows = self._indexed_chunks.list_for_indexing_job(indexing_job_id, statuses=[_INDEXED])
        return self._delete_rows(
            rows,
            collection_name=collection_name,
            removed_by=removed_by,
            reason=reason,
            new_status=_REMOVED,
        )

    def delete_chunk_ids(
        self,
        *,
        knowledge_base_id: str,
        chunk_ids: list[str],
        collection_name: str,
        removed_by: int | None = None,
        reason: str | None = None,
        new_status: str = _REMOVED,
    ) -> DeleteIndexedChunksResult:
        rows = self._indexed_chunks.list_by_chunk_ids(
            chunk_ids,
            knowledge_base_id=knowledge_base_id,
            statuses=[_INDEXED],
        )
        return self._delete_rows(
            rows,
            collection_name=collection_name,
            removed_by=removed_by,
            reason=reason,
            new_status=new_status,
        )

    def _delete_rows(
        self,
        rows,
        *,
        collection_name: str,
        removed_by: int | None,
        reason: str | None,
        new_status: str,
    ) -> DeleteIndexedChunksResult:
        if not rows:
            return DeleteIndexedChunksResult()

        by_collection: dict[str, list] = defaultdict(list)
        for row in rows:
            coll = str(row.qdrant_collection or collection_name or "").strip()
            if coll:
                by_collection[coll].append(row)

        failed_ids: list[str] = []
        qdrant_deleted = 0
        postgres_updated = 0
        now = utc_now_naive().isoformat()
        meta_base = {
            "removed_at": now,
            "removed_by": removed_by,
            "remove_reason": reason,
        }

        for coll, coll_rows in by_collection.items():
            point_ids = [row.qdrant_point_id for row in coll_rows if row.qdrant_point_id]
            delete_result = self._qdrant.delete_points(coll, point_ids)
            qdrant_deleted += delete_result.deleted + delete_result.missing
            failed_ids.extend(delete_result.failed_ids)

            for row in coll_rows:
                status = new_status
                error_code = None
                if row.qdrant_point_id in delete_result.failed_ids:
                    status = _DELETE_FAILED
                    error_code = IndexingErrorCode.QDRANT_DELETE_FAILED.value
                self._indexed_chunks.update_chunk_status(
                    row.id,
                    status=status,
                    error_code=error_code,
                    metadata_patch=meta_base,
                )
                postgres_updated += 1

        error_code = None
        if failed_ids:
            error_code = IndexingErrorCode.QDRANT_DELETE_FAILED.value
        return DeleteIndexedChunksResult(
            requested=len(rows),
            qdrant_deleted=qdrant_deleted,
            postgres_updated=postgres_updated,
            failed_point_ids=tuple(failed_ids),
            error_code=error_code,
        )


__all__ = ["DeleteIndexedChunksService"]
