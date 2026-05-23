# backend/apps/knowledge/service/knowledge_lineage_service.py
# Owns lineage graph assembly and claim enrichment for retrieval explanations.

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from apps.knowledge.errors import KnowledgeValidationError
from apps.knowledge.service.lineage_builder_v0 import LineageBuilderV0
from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0


@dataclass(frozen=True)
class KnowledgeLineageDependencies:
    sentence_store: Any
    knowledge_feedback_service: Any
    load_existing_global_profiles: Callable[..., list[dict[str, Any]]]
    load_existing_retrieval_chunks: Callable[..., list[dict[str, Any]]]


class KnowledgeLineageService:
    def __init__(self, dependencies: KnowledgeLineageDependencies) -> None:
        self._sentence_store = getattr(dependencies, "sentence_store", None)
        self._knowledge_feedback_service = getattr(dependencies, "knowledge_feedback_service", None)
        self._load_existing_global_profiles = getattr(dependencies, "load_existing_global_profiles", lambda **_kwargs: [])
        self._load_existing_retrieval_chunks = getattr(dependencies, "load_existing_retrieval_chunks", lambda **_kwargs: [])

    def enrich_matched_claims_for_explanation(self, matched_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        sentence_cache: dict[str, Any] = {}
        for claim in matched_claims:
            row = dict(claim)
            sentence_ids = [str(item).strip() for item in row.get("sentence_ids") or [] if str(item or "").strip()]
            sentence_texts: list[str] = []
            source_ids = [str(item).strip() for item in row.get("source_ids") or [] if str(item or "").strip()]
            for sentence_id in sentence_ids:
                if sentence_id not in sentence_cache:
                    sentence_cache[sentence_id] = self._sentence_store.get(sentence_id)
                sentence = sentence_cache.get(sentence_id)
                sentence_text = str(getattr(sentence, "text_content", "") or "").strip()
                if sentence_text:
                    sentence_texts.append(sentence_text)
                source_id = str(getattr(sentence, "source_id", "") or "").strip()
                if source_id and source_id not in source_ids:
                    source_ids.append(source_id)
            if sentence_texts:
                row["sentence_text"] = sentence_texts[0]
                row["sentence_texts"] = sentence_texts
            if source_ids:
                row["source_ids"] = source_ids
            enriched.append(row)
        return enriched

    def build_lineage_graph(self, *, corpus_uuid: str) -> dict[str, Any]:
        global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        global_profiles, feedback_events = self._knowledge_feedback_service.apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        global_profiles, source_withdrawal_events = self._knowledge_feedback_service.apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        retrieval_chunks = (
            RetrievalChunkBuilderV0().build_many(global_profiles, [])
            if feedback_events or source_withdrawal_events
            else self._load_existing_retrieval_chunks(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=None,
            )
        )
        graph = LineageBuilderV0().build(global_profiles=global_profiles, retrieval_chunks=retrieval_chunks)
        graph["feedback_events"] = feedback_events
        graph["source_withdrawal_events"] = source_withdrawal_events
        return graph

    def get_lineage(
        self,
        *,
        corpus_uuid: str,
        claim_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        target_type = "claim" if claim_id else "global_profile"
        target_id = str(claim_id or profile_id or "").strip()
        if not target_id:
            raise KnowledgeValidationError("claim_id or profile_id is required.")
        graph = self.build_lineage_graph(corpus_uuid=corpus_uuid)
        focused = LineageBuilderV0().focus(graph, target_type=target_type, target_id=target_id)
        focused["corpus_uuid"] = corpus_uuid
        return focused


__all__ = ["KnowledgeLineageDependencies", "KnowledgeLineageService"]
