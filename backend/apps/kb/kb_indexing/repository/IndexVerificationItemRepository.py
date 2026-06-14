from __future__ import annotations

from apps.kb.kb_indexing.orm.IndexVerificationItem import IndexVerificationItem
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class IndexVerificationItemRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def add_items(self, items: list[IndexVerificationItem]) -> int:
        if not items:
            return 0
        with self._session_factory() as session:
            session.add_all(items)
            session.commit()
        return len(items)

    def build_item(
        self,
        *,
        verification_id: str,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        indexed_chunk_id: str,
        chunk_id: str,
        embedding_id: str,
        qdrant_collection: str,
        qdrant_point_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        payload_found: bool = False,
        vector_found: bool = False,
        chunk_id_match: bool = False,
        knowledge_base_id_match: bool = False,
        training_item_id_match: bool = False,
        vector_hash_match: bool = False,
        payload_valid: bool = False,
        metadata: dict | None = None,
    ) -> IndexVerificationItem:
        now = utc_now_naive()
        return IndexVerificationItem(
            id=new_id("idx_vitem"),
            verification_id=verification_id,
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            indexing_job_id=indexing_job_id,
            indexed_chunk_id=indexed_chunk_id,
            chunk_id=chunk_id,
            embedding_id=embedding_id,
            qdrant_collection=qdrant_collection,
            qdrant_point_id=qdrant_point_id,
            status=status,
            error_code=error_code,
            error_message=(error_message or "")[:4000] or None,
            payload_found=payload_found,
            vector_found=vector_found,
            chunk_id_match=chunk_id_match,
            knowledge_base_id_match=knowledge_base_id_match,
            training_item_id_match=training_item_id_match,
            vector_hash_match=vector_hash_match,
            payload_valid=payload_valid,
            metadata_json=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )


__all__ = ["IndexVerificationItemRepository"]
