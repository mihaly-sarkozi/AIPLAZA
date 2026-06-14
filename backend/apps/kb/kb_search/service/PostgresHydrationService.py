from __future__ import annotations

from typing import Any

from sqlalchemy import select

from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk


class PostgresHydrationService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def hydrate(self, ranked_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunk_ids = [
            str((hit.get("payload") or {}).get("chunk_id") or "").strip()
            for hit in ranked_hits
        ]
        chunk_ids = [cid for cid in chunk_ids if cid]
        chunks_by_id: dict[str, KnowledgeChunk] = {}
        if chunk_ids:
            with self._session_factory() as session:
                rows = list(
                    session.execute(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))
                    .scalars()
                    .all()
                )
                for row in rows:
                    session.expunge(row)
                    chunks_by_id[row.id] = row

        hydrated: list[dict[str, Any]] = []
        for hit in ranked_hits:
            payload = dict(hit.get("payload") or {})
            chunk_id = str(payload.get("chunk_id") or "").strip()
            chunk = chunks_by_id.get(chunk_id)
            text = chunk.text if chunk is not None else str(payload.get("text_preview") or "")
            heading_path = None
            if chunk is not None and chunk.metadata_json:
                heading_path = chunk.metadata_json.get("heading_path")
            elif payload.get("heading_path"):
                heading_path = payload.get("heading_path")
            page_numbers = payload.get("page_numbers") or []
            if chunk is not None and chunk.page_number is not None and not page_numbers:
                page_numbers = [chunk.page_number]
            hydrated.append(
                {
                    **hit,
                    "chunk_id": chunk_id,
                    "training_item_id": str(payload.get("training_item_id") or (chunk.document_id if chunk else "")),
                    "embedding_id": str(payload.get("embedding_id") or ""),
                    "document_title": str(payload.get("document_title") or payload.get("title") or chunk.file_name if chunk else ""),
                    "section_title": chunk.section_title if chunk else payload.get("section_title"),
                    "heading_path": heading_path,
                    "page_numbers": page_numbers,
                    "text": text,
                    "snippet": (text or "")[:480],
                    "keywords": payload.get("keywords") or [],
                    "topics": payload.get("topics") or [],
                    "entities": payload.get("entities") or [],
                    "content_type": payload.get("content_type"),
                    "source_type": payload.get("source_type") or (chunk.source_type if chunk else ""),
                    "source_id": chunk_id,
                }
            )
        return hydrated


__all__ = ["PostgresHydrationService"]
