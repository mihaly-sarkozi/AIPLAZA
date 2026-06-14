from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from apps.kb.kb_crud.adapters.legacy_facade_resolver import resolve_legacy_knowledge_facade
from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter

logger = logging.getLogger(__name__)


class KnowledgeBaseContentCleanup:
    """Tudástár tartalom törlése: Qdrant gyűjtemény + legacy DB/object storage cleanup."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def clear_contents(self, kb_uuid: str, *, confirm_name: str | None = None) -> dict[str, int]:
        collection_name = self._get_collection_name(kb_uuid)
        qdrant_deleted = 0
        if collection_name:
            try:
                if QdrantAdapter().delete_collection(collection_name):
                    qdrant_deleted = 1
            except Exception:
                logger.exception("Qdrant collection törlés hiba (kb=%s)", kb_uuid)

        facade: Any | None = resolve_legacy_knowledge_facade()
        legacy_counts: dict[str, int] = {}
        if facade is not None:
            try:
                legacy_counts = facade.clear_contents(kb_uuid, confirm_name=confirm_name)
            except Exception:
                logger.exception("Legacy KB content cleanup hiba (kb=%s)", kb_uuid)

        if qdrant_deleted:
            legacy_counts = dict(legacy_counts or {})
            legacy_counts["qdrant_collections_deleted"] = qdrant_deleted
        return legacy_counts

    def _get_collection_name(self, kb_uuid: str) -> str | None:
        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM.qdrant_collection_name)
                .where(KnowledgeBaseORM.uuid == kb_uuid)
                .limit(1)
            ).scalar_one_or_none()
        name = str(row or "").strip()
        return name or None


__all__ = ["KnowledgeBaseContentCleanup"]
