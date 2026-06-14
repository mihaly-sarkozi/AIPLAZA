from __future__ import annotations

import logging

from sqlalchemy import select

from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.adapters.QdrantCollectionManager import QdrantCollectionManager
from core.kernel.config.config_loader import settings

logger = logging.getLogger(__name__)


def list_qdrant_collection_names(session_factory, *, include_deleted: bool = False) -> list[str]:
    with session_factory() as session:
        query = select(KnowledgeBaseORM.qdrant_collection_name)
        if not include_deleted:
            query = query.where(KnowledgeBaseORM.deleted_at.is_(None))
        rows = session.execute(query).scalars().all()
    names = [str(name or "").strip() for name in rows]
    return [name for name in names if name]


def delete_qdrant_collections(collection_names: list[str]) -> int:
    adapter = QdrantAdapter()
    deleted = 0
    for name in collection_names:
        if adapter.delete_collection(name):
            deleted += 1
    return deleted


def ensure_kb_qdrant_collection(collection_name: str, *, raise_on_error: bool = False) -> bool:
    name = str(collection_name or "").strip()
    if not name:
        return False
    vector_size = int(getattr(settings, "embedding_vector_size", 1024) or 1024)
    try:
        QdrantCollectionManager(QdrantAdapter()).ensure_collection(
            name,
            vector_size=vector_size,
        )
        return True
    except Exception:
        logger.exception("Qdrant collection ensure sikertelen: %s", name)
        if raise_on_error:
            raise
        return False


__all__ = [
    "delete_qdrant_collections",
    "ensure_kb_qdrant_collection",
    "list_qdrant_collection_names",
]
