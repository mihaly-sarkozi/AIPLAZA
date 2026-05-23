from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.candidate_selection import entity_candidate_to_json_dict
from apps.knowledge.domain.decision_analysis import decision_analysis_to_json_dict
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.search_profile import search_profile_to_json_dict
from apps.knowledge.domain.semantic_block import semantic_block_to_json_dict
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.technical_entity import technical_entity_to_json_dict
from apps.knowledge.domain.technical_memory_chunk import technical_memory_chunk_to_json_dict
from apps.knowledge.domain.tension_analysis import tension_analysis_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
from apps.knowledge.service.decision_engine_v1 import DecisionEngineV1
from apps.knowledge.service.global_profile_builder_v0 import GlobalProfileBuilderV0
from apps.knowledge.service.local_resolver_v1 import attach_local_resolver_metadata
from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1
from apps.knowledge.service.semantic_block_builder_v1 import SemanticBlockBuilderV1
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1
from apps.knowledge.service.tension_engine_v1 import TensionEngineV1


@dataclass(frozen=True)
class InterpretationArtifacts:
    metadata: dict[str, Any]
    local_entity_cluster_count: int


class InterpretationArtifactBuilder:
    def __init__(
        self,
        *,
        load_existing_semantic_blocks: Callable[..., list[dict[str, Any]]],
        load_existing_search_profiles: Callable[..., list[Any]],
        load_existing_global_profiles: Callable[..., list[Any]],
    ) -> None:
        self._load_existing_semantic_blocks = load_existing_semantic_blocks
        self._load_existing_search_profiles = load_existing_search_profiles
        self._load_existing_global_profiles = load_existing_global_profiles

    def build_metadata(
        self,
        *,
        run: InterpretationRun,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        claims: list[Claim],
        local_clusters: list[LocalEntityCluster],
        local_resolver_trace: dict[str, Any],
        sentence_interpretation_count: int,
        mention_count: int,
        space_time_frame_count: int,
        quality_summary: dict[str, Any],
    ) -> InterpretationArtifacts:
        semantic_blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)
        semantic_block_payload = self._semantic_block_payload(source=source, run=run, semantic_blocks=semantic_blocks)
        technical_entities = TechnicalEntityBuilderV1().build(local_clusters, claims=claims)
        technical_entity_payload = [technical_entity_to_json_dict(item) for item in technical_entities]
        technical_memory_chunks = TechnicalMemoryChunkBuilderV1().build_many(technical_entities)
        technical_memory_chunk_payload = [
            technical_memory_chunk_to_json_dict(item) for item in technical_memory_chunks
        ]
        search_profiles = SearchProfileBuilderV1().build_many(technical_memory_chunks)
        search_profile_payload = [search_profile_to_json_dict(item) for item in search_profiles]
        stored_search_profiles = self._load_existing_search_profiles(
            corpus_uuid=source.corpus_uuid,
            exclude_interpretation_run_id=run.id,
        )
        stored_global_profiles = self._load_existing_global_profiles(
            corpus_uuid=source.corpus_uuid,
            exclude_interpretation_run_id=run.id,
        )
        candidate_profile_pool = stored_search_profiles or search_profiles
        candidate_selections = CandidateSelectionV1().select_many(
            search_profiles,
            existing_profiles=stored_search_profiles if stored_search_profiles else None,
            limit_per_profile=3,
        )
        similarity_analyses = SimilarityEngineV1().analyze_many(
            search_profiles,
            candidate_selections,
            candidate_profile_pool,
        )
        decision_analyses = DecisionEngineV1().decide_many(
            search_profiles,
            candidate_selections,
            similarity_analyses,
            tensions=[],
        )
        global_profiles = GlobalProfileBuilderV0().build_many(
            decision_analyses,
            search_profiles,
            candidate_profiles=candidate_profile_pool,
            existing_global_profiles=stored_global_profiles,
        )
        tension_analyses = [
            *TensionEngineV1().analyze_many(search_profiles, similarity_analyses, candidate_profile_pool),
            *TensionEngineV1().analyze_global_profiles(global_profiles),
        ]
        tension_analysis_payload = [tension_analysis_to_json_dict(item) for item in tension_analyses]
        retrieval_chunks = RetrievalChunkBuilderV0().build_many(global_profiles, tension_analysis_payload)
        metadata = attach_local_resolver_metadata(
            {
                **run.metadata,
                "sentence_interpretation_count": sentence_interpretation_count,
                "mention_count": mention_count,
                "claim_count": len(claims),
                "space_time_frame_count": space_time_frame_count,
                "quality_summary": quality_summary,
                **self._semantic_block_metadata(semantic_blocks, semantic_block_payload),
                "technical_entity_builder_version": TechnicalEntityBuilderV1.version,
                "technical_entity_count": len(technical_entities),
                "technical_entities": technical_entity_payload,
                "technical_memory_chunk_builder_version": TechnicalMemoryChunkBuilderV1.version,
                "technical_memory_chunk_count": len(technical_memory_chunks),
                "technical_memory_chunks": technical_memory_chunk_payload,
                "search_profile_builder_version": SearchProfileBuilderV1.version,
                "search_profile_count": len(search_profiles),
                "search_profiles": search_profile_payload,
                "candidate_selection_builder_version": CandidateSelectionV1.version,
                "candidate_selection_attempted_count": candidate_selection_attempt_count(
                    search_profiles,
                    existing_profiles=stored_search_profiles if stored_search_profiles else None,
                ),
                "candidate_pool_size": len(candidate_profile_pool),
                "candidate_selection_count": len(candidate_selections),
                "candidate_selections": [entity_candidate_to_json_dict(item) for item in candidate_selections],
                "similarity_engine_version": SimilarityEngineV1.version,
                "similarity_analysis_count": len(similarity_analyses),
                "similarity_analyses": [similarity_analysis_to_json_dict(item) for item in similarity_analyses],
                "tension_engine_version": TensionEngineV1.version,
                "tension_analysis_count": len(tension_analyses),
                "tension_analyses": tension_analysis_payload,
                "retrieval_chunk_builder_version": RetrievalChunkBuilderV0.version,
                "retrieval_chunk_count": len(retrieval_chunks),
                "retrieval_chunks": retrieval_chunks,
                "decision_engine_version": DecisionEngineV1.version,
                "decision_analysis_count": len(decision_analyses),
                "decision_analyses": [decision_analysis_to_json_dict(item) for item in decision_analyses],
                "global_profile_builder_version": GlobalProfileBuilderV0.version,
                "global_profile_count": len(global_profiles),
                "global_profiles": global_profiles,
            },
            clusters=local_clusters,
            trace=local_resolver_trace,
        )
        return InterpretationArtifacts(metadata=metadata, local_entity_cluster_count=len(local_clusters))

    def _semantic_block_payload(
        self,
        *,
        source: Source,
        run: InterpretationRun,
        semantic_blocks: list[Any],
    ) -> list[dict[str, Any]]:
        payload = [semantic_block_to_json_dict(item) for item in semantic_blocks]
        return enrich_semantic_blocks_with_quality(
            payload,
            existing_blocks=self._load_existing_semantic_blocks(
                corpus_uuid=source.corpus_uuid,
                exclude_interpretation_run_id=run.id,
            ),
            source_type=source.source_type,
        )

    @staticmethod
    def _semantic_block_metadata(semantic_blocks: list[Any], payload: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "semantic_block_builder_version": SemanticBlockBuilderV1.version,
            "semantic_block_count": len(semantic_blocks),
            "semantic_blocks": payload,
            "semantic_block_conflict_count": sum(int(item.get("conflict_count") or 0) for item in payload),
            "semantic_block_disputed_count": sum(1 for item in payload if item.get("block_status") == "disputed"),
        }


__all__ = ["InterpretationArtifactBuilder", "InterpretationArtifacts"]
