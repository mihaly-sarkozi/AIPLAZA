from __future__ import annotations

from typing import Any

from sqlalchemy import select

from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic
from apps.kb.kb_discovery.orm.ProcessMention import ProcessMention
from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention
from apps.kb.kb_discovery.orm.TemporalMention import TemporalMention
from apps.kb.kb_discovery.repository.EntityRepository import EntityRepository
from apps.kb.kb_processing.adapters.step_preview_helpers import (
    _PREVIEW_LIMIT,
    format_relation_label,
    text_snippet,
)
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.NormalizedContentPart import NormalizedContentPart
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository


class ProcessingStepOutputEnricher:
    """Lépés kimenet kiegészítése ellenőrizhető előnézeti listákkal (DB-ből)."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._entity_repository = EntityRepository(session_factory)
        self._content_repository = ContentRepository(session_factory)
        self._chunk_repository = ChunkRepository(session_factory)

    def enrich(
        self,
        *,
        module: str,
        step: str,
        training_item_id: str | None,
        output_summary_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not training_item_id:
            return dict(output_summary_json or {})

        handlers: dict[tuple[str, str], Any] = {
            ("kb_discovery", "EXTRACT_ENTITIES"): self._enrich_entities,
            ("kb_discovery", "ENRICH_LOCAL"): self._enrich_enrichment,
            ("kb_discovery", "EXTRACT_TEMPORAL"): self._enrich_temporal,
            ("kb_discovery", "EXTRACT_SPATIAL"): self._enrich_spatial,
            ("kb_discovery", "EXTRACT_PROCESS"): self._enrich_process,
            ("kb_discovery", "BUILD_RELATIONSHIPS"): self._enrich_relationships,
            ("kb_discovery", "SCORE_KNOWLEDGE"): self._enrich_scores,
            ("kb_understanding", "EXTRACT_CONTENT"): self._enrich_extracted_parts,
            ("kb_understanding", "NORMALIZE_PARTS"): self._enrich_normalized_parts,
            ("kb_understanding", "BUILD_CHUNKS"): self._enrich_chunks,
        }
        handler = handlers.get((module, step))
        if handler is None:
            return dict(output_summary_json or {})
        return handler(training_item_id, dict(output_summary_json or {}))

    def _enrich_entities(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("entities"):
            return output
        entities = self._entity_repository.list_for_document(training_item_id)
        if not entities:
            return output
        top_entities = sorted(entities, key=lambda entity: entity.confidence, reverse=True)[:_PREVIEW_LIMIT]
        output["entities"] = [
            {
                "name": entity.name,
                "type": entity.entity_type,
                "confidence": round(float(entity.confidence), 4),
            }
            for entity in top_entities
        ]
        return output

    def _enrich_enrichment(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if not output.get("keywords"):
            output["keywords"] = self._load_keywords_preview(training_item_id)
        if not output.get("topics"):
            output["topics"] = self._load_topics_preview(training_item_id)
        return output

    def _enrich_temporal(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("temporal_mentions"):
            return output
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(TemporalMention)
                    .where(TemporalMention.training_item_id == training_item_id)
                    .order_by(TemporalMention.confidence.desc())
                    .limit(_PREVIEW_LIMIT)
                ).scalars()
            )
        output["temporal_mentions"] = [
            {
                "text": row.raw_text,
                "type": row.temporal_type,
                "confidence": round(float(row.confidence), 4),
            }
            for row in rows
        ]
        return output

    def _enrich_spatial(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("spatial_mentions"):
            return output
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(SpatialMention)
                    .where(SpatialMention.training_item_id == training_item_id)
                    .order_by(SpatialMention.confidence.desc())
                    .limit(_PREVIEW_LIMIT)
                ).scalars()
            )
        output["spatial_mentions"] = [
            {
                "text": row.raw_text or row.normalized_location,
                "location_type": row.location_type,
                "confidence": round(float(row.confidence), 4),
            }
            for row in rows
        ]
        return output

    def _enrich_process(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("process_mentions"):
            return output
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(ProcessMention)
                    .where(ProcessMention.training_item_id == training_item_id)
                    .order_by(ProcessMention.confidence.desc(), ProcessMention.step_order.asc().nullsfirst())
                    .limit(_PREVIEW_LIMIT)
                ).scalars()
            )
        output["process_mentions"] = [
            {
                "process_name": row.process_name,
                "step_text": text_snippet(row.step_text, max_len=120),
                "confidence": round(float(row.confidence), 4),
            }
            for row in rows
        ]
        return output

    def _enrich_relationships(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("relationships"):
            return output
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeRelationship)
                    .where(KnowledgeRelationship.training_item_id == training_item_id)
                    .order_by(KnowledgeRelationship.confidence.desc())
                    .limit(_PREVIEW_LIMIT)
                ).scalars()
            )
        output["relationships"] = [
            {
                "from_label": format_relation_label(row.from_type, row.from_id),
                "relation": row.relation,
                "to_label": format_relation_label(row.to_type, row.to_id),
                "confidence": round(float(row.confidence), 4),
            }
            for row in rows
        ]
        return output

    def _enrich_scores(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("scores"):
            return output
        chunks = self._chunk_repository.list_for_document(training_item_id)
        if not chunks:
            return output
        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        chunk_ids = list(chunk_by_id.keys())
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeScore)
                    .where(KnowledgeScore.chunk_id.in_(chunk_ids))
                    .order_by(KnowledgeScore.knowledge_score.desc())
                    .limit(_PREVIEW_LIMIT)
                ).scalars()
            )
        output["scores"] = [
            {
                "chunk_index": (chunk_by_id[row.chunk_id].order_index + 1)
                if row.chunk_id in chunk_by_id
                else None,
                "chunk_type": chunk_by_id[row.chunk_id].chunk_type if row.chunk_id in chunk_by_id else "",
                "score": round(float(row.knowledge_score), 4),
                "snippet": text_snippet(chunk_by_id[row.chunk_id].text)
                if row.chunk_id in chunk_by_id
                else "",
            }
            for row in rows
        ]
        return output

    def _enrich_extracted_parts(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("blocks"):
            return output
        parts = self._content_repository.list_parts_for_item(training_item_id)[:_PREVIEW_LIMIT]
        output["blocks"] = [
            {
                "part_type": part.part_type,
                "page": part.page_number,
                "char_count": part.char_count,
                "snippet": text_snippet(part.text),
            }
            for part in parts
        ]
        return output

    def _enrich_normalized_parts(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("blocks"):
            return output
        parts = self._content_repository.list_normalized_parts_for_item(training_item_id)[:_PREVIEW_LIMIT]
        output["blocks"] = [
            {
                "part_type": part.part_type,
                "page": part.page_number,
                "char_count": len(part.normalized_text or ""),
                "snippet": text_snippet(part.normalized_text),
            }
            for part in parts
        ]
        return output

    def _enrich_chunks(self, training_item_id: str, output: dict[str, Any]) -> dict[str, Any]:
        if output.get("chunks"):
            return output
        chunks = self._chunk_repository.list_for_document(training_item_id)[:_PREVIEW_LIMIT]
        output["chunks"] = [
            {
                "index": chunk.order_index + 1,
                "chunk_type": chunk.chunk_type,
                "page": chunk.page_number,
                "tokens": chunk.token_count,
                "language_code": chunk.language_code,
                "snippet": text_snippet(chunk.text),
            }
            for chunk in chunks
        ]
        return output

    def _load_keywords_preview(self, training_item_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeKeyword)
                    .where(KnowledgeKeyword.training_item_id == training_item_id)
                    .order_by(KnowledgeKeyword.confidence.desc(), KnowledgeKeyword.score.desc())
                    .limit(200)
                ).scalars()
            )
        seen: set[str] = set()
        preview: list[dict[str, Any]] = []
        for row in rows:
            key = row.normalized_term
            if key in seen:
                continue
            seen.add(key)
            preview.append(
                {
                    "term": row.display_term or row.term,
                    "language_code": row.language_code,
                    "confidence": round(float(row.confidence), 4),
                }
            )
            if len(preview) >= _PREVIEW_LIMIT:
                break
        return preview

    def _load_topics_preview(self, training_item_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeTopic)
                    .where(KnowledgeTopic.training_item_id == training_item_id)
                    .order_by(KnowledgeTopic.confidence.desc(), KnowledgeTopic.score.desc())
                    .limit(200)
                ).scalars()
            )
        seen: set[str] = set()
        preview: list[dict[str, Any]] = []
        for row in rows:
            key = row.topic_key
            if key in seen:
                continue
            seen.add(key)
            preview.append(
                {
                    "name": row.display_name or row.normalized_topic or row.topic_key,
                    "topic_key": row.topic_key,
                    "confidence": round(float(row.confidence), 4),
                }
            )
            if len(preview) >= _PREVIEW_LIMIT:
                break
        return preview


__all__ = ["ProcessingStepOutputEnricher"]
