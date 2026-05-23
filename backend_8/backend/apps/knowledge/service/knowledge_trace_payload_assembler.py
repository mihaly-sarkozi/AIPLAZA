from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.candidate_selection import entity_candidate_to_json_dict
from apps.knowledge.domain.local_entity_cluster import local_entity_cluster_to_json_dict
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.domain.technical_entity import technical_entity_to_json_dict
from apps.knowledge.domain.technical_memory_chunk import technical_memory_chunk_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
from apps.knowledge.service.knowledge_trace_metrics import (
    bad_subject_claim_examples as _bad_subject_claim_examples,
    candidate_group_count as _candidate_group_count,
    candidate_selection_ready as _candidate_selection_ready,
    candidates_without_evidence_count as _candidates_without_evidence_count,
    canonical_entity_merge_suggestion_count as _canonical_entity_merge_suggestion_count,
    conflict_count as _conflict_count,
    dedupe_candidate_selection_dicts as _dedupe_candidate_selection_dicts,
    dedupe_similarity_analysis_dicts as _dedupe_similarity_analysis_dicts,
    duplicate_memory_profile_count as _duplicate_memory_profile_count,
    hard_conflict_count as _hard_conflict_count,
    is_uuid_string as _is_uuid_string,
    multilingual_alias_match_count as _multilingual_alias_match_count,
    reason_values as _reason_values,
    similarity_band_count as _similarity_band_count,
    similarity_boost_reason_count as _similarity_boost_reason_count,
    similarity_ready as _similarity_ready,
    similarity_score_distribution as _similarity_score_distribution,
    similarity_without_evidence_count as _similarity_without_evidence_count,
    tension_band_count as _tension_band_count,
    tension_type_count as _tension_type_count,
    tension_without_evidence_count as _tension_without_evidence_count,
    top_candidate_score as _top_candidate_score,
    unknown_entity_type_examples as _unknown_entity_type_examples,
)
from apps.knowledge.service.knowledge_trace_payload_builder import (
    _affected_profile_ids,
    _attach_decisions_to_entity_rows,
    _decision_kind_count,
    _decision_manual_review_count,
    _decision_ready,
    _global_profile_claim_count,
    _global_profile_operation_count,
    _is_missing_table_error,
    _local_entity_summary_counts,
    _near_duplicate_guard_trigger_count,
    _normalize_local_entity_trace_dict,
    _retrieval_conflicting_chunk_count,
    _retrieval_temporal_context_included,
    _search_profile_from_dict,
    _technical_entity_trace_dict,
    _tension_ready,
    _timeline_compatibility_reasons,
)
from apps.knowledge.service.knowledge_trace_quality_summary import quality_summary_from_run as _quality_summary_from_run
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1

logger = logging.getLogger(__name__)


class KnowledgeTracePayloadAssembler:
    def __init__(
        self,
        *,
        local_entity_cluster_repository: Any | None = None,
    ) -> None:
        self._local_entity_cluster_repository = local_entity_cluster_repository

    def build(self, *, query: Any, interpretation: Any | None) -> dict[str, Any]:
        run = query.run
        primary_item = query.primary_item
        source_id = query.source_id
        source = query.source
        document = query.document
        sentence_rows = query.sentence_rows
        total_mentions = query.total_mentions
        total_claims = query.total_claims
        total_space_time_frames = query.total_space_time_frames
        negative_claim_count = query.negative_claim_count
        subj_ctx_counters = query.subj_ctx_counters
        language = query.language

        interpretation_meta = dict(getattr(interpretation, "metadata", {}) or {}) if interpretation is not None else {}
        local_cluster_count_meta = int(interpretation_meta.get("local_entity_cluster_count") or 0)
        local_clusters = _dict_list(interpretation_meta.get("local_entity_clusters"))
        technical_entities = [
            _technical_entity_trace_dict(item, idx)
            for idx, item in enumerate(_dict_list(interpretation_meta.get("technical_entities")), start=1)
        ]
        technical_memory_chunks = _dict_list(interpretation_meta.get("technical_memory_chunks"))
        search_profiles = _dict_list(interpretation_meta.get("search_profiles"))
        semantic_blocks = _dict_list(interpretation_meta.get("semantic_blocks"))
        candidate_selections = _dict_list(interpretation_meta.get("candidate_selections"))
        similarity_analyses = _dict_list(interpretation_meta.get("similarity_analyses"))
        tension_analyses = _dict_list(interpretation_meta.get("tension_analyses"))
        decision_analyses = _dict_list(interpretation_meta.get("decision_analyses"))
        global_profiles = _dict_list(interpretation_meta.get("global_profiles"))
        retrieval_chunks = _dict_list(interpretation_meta.get("retrieval_chunks"))
        local_resolver_trace = interpretation_meta.get("local_resolver_trace")
        if local_resolver_trace is not None and not isinstance(local_resolver_trace, dict):
            local_resolver_trace = None
        candidate_selection_attempted_count = int(interpretation_meta.get("candidate_selection_attempted_count") or 0)
        candidate_pool_size = int(interpretation_meta.get("candidate_pool_size") or 0)

        candidate_selections, candidate_duplicate_removed_count = _dedupe_candidate_selection_dicts(candidate_selections)
        similarity_analyses, similarity_duplicate_removed_count = _dedupe_similarity_analysis_dicts(similarity_analyses)

        local_entities_raw, local_cluster_rows = self._load_local_entities(
            run_id=run.id,
            interpretation=interpretation,
            local_clusters=local_clusters,
        )

        if not technical_entities and local_cluster_rows:
            technical_entity_objects = TechnicalEntityBuilderV1().build_many(local_cluster_rows)
            technical_entities = [technical_entity_to_json_dict(item) for item in technical_entity_objects]
            if not technical_memory_chunks:
                technical_memory_chunk_objects = TechnicalMemoryChunkBuilderV1().build_many(technical_entity_objects)
                technical_memory_chunks = [technical_memory_chunk_to_json_dict(item) for item in technical_memory_chunk_objects]
                if not search_profiles:
                    search_profile_objects = SearchProfileBuilderV1().build_many(technical_memory_chunk_objects)
                    search_profiles = [item for item in map(_search_profile_to_json_dict, search_profile_objects)]
                    if not candidate_selections:
                        candidate_selection_objects = CandidateSelectionV1().select_many(search_profile_objects, limit_per_profile=3)
                        candidate_selections = [entity_candidate_to_json_dict(item) for item in candidate_selection_objects]
                        if not similarity_analyses:
                            similarity_analysis_objects = SimilarityEngineV1().analyze_many(
                                search_profile_objects,
                                candidate_selection_objects,
                                search_profile_objects,
                            )
                            similarity_analyses = [
                                similarity_analysis_to_json_dict(item) for item in similarity_analysis_objects
                            ]
            technical_entities = [
                _technical_entity_trace_dict(item, idx)
                for idx, item in enumerate(technical_entities, start=1)
            ]

        search_profile_objects_for_matching = [_search_profile_from_dict(item) for item in search_profiles]
        if search_profile_objects_for_matching:
            candidate_pool_size = candidate_pool_size or len(search_profile_objects_for_matching)
            candidate_selection_attempted_count = candidate_selection_attempted_count or candidate_selection_attempt_count(
                search_profile_objects_for_matching
            )
        if search_profile_objects_for_matching and not candidate_selections:
            candidate_selection_objects = CandidateSelectionV1().select_many(
                search_profile_objects_for_matching,
                limit_per_profile=3,
            )
            candidate_selections = [entity_candidate_to_json_dict(item) for item in candidate_selection_objects]
        if search_profile_objects_for_matching and candidate_selections and not similarity_analyses:
            candidate_selection_objects = CandidateSelectionV1().select_many(
                search_profile_objects_for_matching,
                limit_per_profile=3,
            )
            similarity_analysis_objects = SimilarityEngineV1().analyze_many(
                search_profile_objects_for_matching,
                candidate_selection_objects,
                search_profile_objects_for_matching,
            )
            similarity_analyses = [similarity_analysis_to_json_dict(item) for item in similarity_analysis_objects]

        candidate_selections, generated_duplicate_removed_count = _dedupe_candidate_selection_dicts(candidate_selections)
        candidate_duplicate_removed_count += generated_duplicate_removed_count
        similarity_analyses, generated_similarity_duplicate_removed_count = _dedupe_similarity_analysis_dicts(
            similarity_analyses
        )
        similarity_duplicate_removed_count += generated_similarity_duplicate_removed_count

        local_entities = [_normalize_local_entity_trace_dict(item) for item in local_entities_raw]
        local_entities = _attach_decisions_to_entity_rows(local_entities, decision_analyses)
        technical_entities = _attach_decisions_to_entity_rows(technical_entities, decision_analyses)
        search_profiles = _attach_decisions_to_entity_rows(search_profiles, decision_analyses)
        le_stats = _local_entity_summary_counts(local_entities)
        effective_cluster_count = le_stats["local_entity_count"] if le_stats["local_entity_count"] else local_cluster_count_meta

        quality_summary = _build_quality_summary(run, subj_ctx_counters)
        unknown_entity_type_examples = _unknown_entity_type_examples(local_entities)
        bad_subject_claim_examples = list(quality_summary.get("bad_subject_claim_examples") or [])
        multilingual_alias_match_count = _multilingual_alias_match_count(candidate_selections, similarity_analyses)
        canonical_entity_merge_suggestion_count = _canonical_entity_merge_suggestion_count(similarity_analyses)

        return {
            "run_id": run.id,
            "source_id": source_id or None,
            "source_name": source.title if source is not None else (primary_item.display_name if primary_item is not None else None),
            "language": language or "unknown",
            "status": run.status,
            "created_at": run.created_at,
            "summary": _build_summary(
                sentence_rows=sentence_rows,
                total_mentions=total_mentions,
                total_claims=total_claims,
                total_space_time_frames=total_space_time_frames,
                semantic_blocks=semantic_blocks,
                effective_cluster_count=effective_cluster_count,
                technical_entities=technical_entities,
                technical_memory_chunks=technical_memory_chunks,
                search_profiles=search_profiles,
                candidate_selection_attempted_count=candidate_selection_attempted_count,
                candidate_pool_size=candidate_pool_size,
                candidate_selections=candidate_selections,
                candidate_duplicate_removed_count=candidate_duplicate_removed_count,
                similarity_analyses=similarity_analyses,
                similarity_duplicate_removed_count=similarity_duplicate_removed_count,
                quality_summary=quality_summary,
                multilingual_alias_match_count=multilingual_alias_match_count,
                canonical_entity_merge_suggestion_count=canonical_entity_merge_suggestion_count,
                tension_analyses=tension_analyses,
                decision_analyses=decision_analyses,
                global_profiles=global_profiles,
                retrieval_chunks=retrieval_chunks,
                local_resolver_trace=local_resolver_trace,
                local_entities=local_entities,
                le_stats=le_stats,
                unknown_entity_type_examples=unknown_entity_type_examples,
                bad_subject_claim_examples=bad_subject_claim_examples,
                negative_claim_count=negative_claim_count,
                local_cluster_count_meta=local_cluster_count_meta,
                subj_ctx_counters=subj_ctx_counters,
            ),
            "sentences": sentence_rows,
            "local_entities": local_entities,
            "local_entity_clusters": local_clusters,
            "technical_entities": technical_entities,
            "technical_memory_chunks": technical_memory_chunks,
            "search_profiles": search_profiles,
            "semantic_blocks": semantic_blocks,
            "candidate_selections": candidate_selections,
            "similarity_analyses": similarity_analyses,
            "tension_analyses": tension_analyses,
            "decision_analyses": decision_analyses,
            "global_profiles": global_profiles,
            "retrieval_chunks": retrieval_chunks,
            "local_resolver_trace": local_resolver_trace,
        }

    def _load_local_entities(
        self,
        *,
        run_id: str,
        interpretation: Any | None,
        local_clusters: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[Any]]:
        local_entities_raw: list[dict[str, Any]] = []
        local_cluster_rows: list[Any] = []
        if interpretation is not None and self._local_entity_cluster_repository is not None:
            interp_id = getattr(interpretation, "id", None)
            if interp_id is not None and _is_uuid_string(str(interp_id)):
                try:
                    rows = self._local_entity_cluster_repository.list_by_run(interp_id)
                    local_cluster_rows = list(rows)
                    local_entities_raw = [local_entity_cluster_to_json_dict(item) for item in local_cluster_rows]
                except ProgrammingError as exc:
                    if _is_missing_table_error(exc, "knowledge_local_entity_clusters"):
                        logger.warning(
                            "knowledge.trace.skip_missing_local_entity_clusters",
                            extra={"run_id": run_id, "interpretation_run_id": str(interp_id)},
                        )
                    else:
                        raise
        if not local_entities_raw and local_clusters:
            local_entities_raw = [item for item in local_clusters if isinstance(item, dict)]
        return local_entities_raw, local_cluster_rows


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _search_profile_to_json_dict(item: Any) -> dict[str, Any]:
    from apps.knowledge.domain.search_profile import search_profile_to_json_dict

    return search_profile_to_json_dict(item)


def _build_quality_summary(run: Any, subj_ctx_counters: dict[str, int]) -> dict[str, Any]:
    quality_summary = _quality_summary_from_run(run)
    quality_summary["context_carryover_blocked_due_to_explicit_subject_count"] = int(
        subj_ctx_counters["explicit_subject_kept"]
    )
    quality_summary["temporal_subject_sanitized_count"] = int(subj_ctx_counters["temporal_subject_sanitized"])
    existing_weak_rejected = int(quality_summary.get("weak_auxiliary_claim_rejected_count") or 0)
    quality_summary["weak_auxiliary_claim_rejected_count"] = existing_weak_rejected + int(
        subj_ctx_counters["weak_auxiliary_subject_stripped"]
    )
    quality_summary.setdefault("noise_sentence_skipped_count", 0)
    quality_summary.setdefault("noise_claim_rejected_count", 0)
    quality_summary["rejected_noise_sentence_count"] = int(
        quality_summary.get("noise_sentence_skipped_count")
        or quality_summary.get("skipped_noise_sentence_count")
        or 0
    )
    quality_summary["bad_subject_claim_examples"] = _bad_subject_claim_examples(quality_summary)
    quality_summary["duplicate_weak_claim_rejected_count"] = int(
        quality_summary.get("duplicate_weak_claim_rejected_count") or 0
    ) + int(subj_ctx_counters["duplicate_weak_compatible"])
    quality_summary.setdefault("carryover_subject_error_count", 0)
    return quality_summary


def _build_summary(**kwargs: Any) -> dict[str, Any]:
    sentence_rows = kwargs["sentence_rows"]
    total_mentions = kwargs["total_mentions"]
    total_claims = kwargs["total_claims"]
    total_space_time_frames = kwargs["total_space_time_frames"]
    semantic_blocks = kwargs["semantic_blocks"]
    effective_cluster_count = kwargs["effective_cluster_count"]
    technical_entities = kwargs["technical_entities"]
    technical_memory_chunks = kwargs["technical_memory_chunks"]
    search_profiles = kwargs["search_profiles"]
    candidate_selections = kwargs["candidate_selections"]
    similarity_analyses = kwargs["similarity_analyses"]
    quality_summary = kwargs["quality_summary"]
    tension_analyses = kwargs["tension_analyses"]
    decision_analyses = kwargs["decision_analyses"]
    global_profiles = kwargs["global_profiles"]
    retrieval_chunks = kwargs["retrieval_chunks"]
    local_resolver_trace = kwargs["local_resolver_trace"]
    le_stats = kwargs["le_stats"]
    subj_ctx_counters = kwargs["subj_ctx_counters"]
    return {
        "sentence_count": len(sentence_rows),
        "mention_count": total_mentions,
        "claim_count": total_claims,
        "space_time_frame_count": total_space_time_frames,
        "semantic_block_count": len(semantic_blocks),
        "local_entity_cluster_count": effective_cluster_count,
        "technical_entities": len(technical_entities),
        "technical_memory_chunks": len(technical_memory_chunks),
        "search_profiles": len(search_profiles),
        "candidate_selection_attempted_count": kwargs["candidate_selection_attempted_count"],
        "candidate_pool_size": kwargs["candidate_pool_size"],
        "candidate_selection_count": len(candidate_selections),
        "candidate_group_count": _candidate_group_count(candidate_selections),
        "duplicate_memory_profile_count": _duplicate_memory_profile_count(candidate_selections),
        "candidates_found_count": len(candidate_selections),
        "candidates_without_evidence_count": _candidates_without_evidence_count(candidate_selections),
        "top_candidate_score": _top_candidate_score(candidate_selections),
        "candidate_selection_ready": _candidate_selection_ready(candidate_selections),
        "similarity_analysis_count": len(similarity_analyses),
        "similarity_score_distribution": _similarity_score_distribution(similarity_analyses),
        "similarity_ready": _similarity_ready(similarity_analyses),
        "high_similarity_count": _similarity_band_count(similarity_analyses, "high"),
        "medium_similarity_count": _similarity_band_count(similarity_analyses, "medium"),
        "low_similarity_count": _similarity_band_count(similarity_analyses, "low"),
        "similarity_without_evidence_count": _similarity_without_evidence_count(similarity_analyses),
        "rejected_noise_sentence_count": quality_summary["rejected_noise_sentence_count"],
        "multilingual_alias_match_count": kwargs["multilingual_alias_match_count"],
        "candidate_duplicate_removed_count": kwargs["candidate_duplicate_removed_count"],
        "similarity_duplicate_removed_count": kwargs["similarity_duplicate_removed_count"],
        "canonical_entity_merge_suggestion_count": kwargs["canonical_entity_merge_suggestion_count"],
        "similarity_boost_reason_count": _similarity_boost_reason_count(similarity_analyses),
        "similarity_boost_reasons": [
            reason
            for reason in _reason_values(similarity_analyses, "similarity_reasons")
            if "boost" in reason or reason.startswith("name:canonical")
        ],
        "tension_analysis_count": len(tension_analyses),
        "tension_count": len(tension_analyses),
        "tension_ready": _tension_ready(tension_analyses),
        "high_tension_count": _tension_band_count(tension_analyses, "high"),
        "medium_tension_count": _tension_band_count(tension_analyses, "medium"),
        "low_tension_count": _tension_band_count(tension_analyses, "low"),
        "conflict_count": _conflict_count(tension_analyses),
        "hard_conflict_count": _hard_conflict_count(tension_analyses),
        "soft_conflict_count": _tension_type_count(tension_analyses, "soft_conflict"),
        "contradiction_count": _tension_type_count(tension_analyses, "contradiction"),
        "temporal_change_count": _tension_type_count(tension_analyses, "temporal_change"),
        "timeline_compatibility_reason_count": len(_timeline_compatibility_reasons(tension_analyses)),
        "timeline_compatibility_reasons": _timeline_compatibility_reasons(tension_analyses),
        "tension_without_evidence_count": _tension_without_evidence_count(tension_analyses),
        "decision_analysis_count": len(decision_analyses),
        "decision_count": len(decision_analyses),
        "global_profile_count": len(global_profiles),
        "global_profile_update_count": _global_profile_operation_count(global_profiles, "update"),
        "global_profile_create_count": _global_profile_operation_count(global_profiles, "create"),
        "global_profile_attach_count": _global_profile_operation_count(global_profiles, "update"),
        "affected_profile_ids": _affected_profile_ids(global_profiles),
        "claim_added_count": _global_profile_claim_count(global_profiles, "claim_added_count"),
        "claim_deduplicated_count": _global_profile_claim_count(global_profiles, "claim_deduplicated_count"),
        "retrieval_chunk_count": len(retrieval_chunks),
        "conflicting_chunk_count": _retrieval_conflicting_chunk_count(retrieval_chunks),
        "temporal_context_included": _retrieval_temporal_context_included(retrieval_chunks),
        "decision_ready": _decision_ready(decision_analyses),
        "attach_existing_count": _decision_kind_count(decision_analyses, "attach_existing"),
        "auto_attach_count": _decision_kind_count(decision_analyses, "attach_existing"),
        "merge_required_count": _decision_kind_count(decision_analyses, "merge_required"),
        "uncertain_match_count": _decision_kind_count(decision_analyses, "uncertain_match"),
        "create_new_profile_count": _decision_kind_count(decision_analyses, "create_new_profile"),
        "create_new_count": _decision_kind_count(decision_analyses, "create_new", "create_new_profile"),
        "keep_separate_count": _decision_kind_count(decision_analyses, "keep_separate"),
        "mark_conflict_count": _decision_kind_count(decision_analyses, "mark_conflict"),
        "near_duplicate_guard_trigger_count": _near_duplicate_guard_trigger_count(decision_analyses, local_resolver_trace),
        "needs_review_count": _decision_kind_count(decision_analyses, "needs_review", "uncertain_match", "merge_required"),
        "manual_review_count": _decision_manual_review_count(decision_analyses),
        "local_entity_count": le_stats["local_entity_count"],
        "low_coherence_local_entity_count": le_stats["low_coherence_local_entity_count"],
        "unknown_entity_type_count": le_stats["unknown_entity_type_count"],
        "unknown_entity_type_examples": kwargs["unknown_entity_type_examples"],
        "bad_subject_claim_examples": kwargs["bad_subject_claim_examples"],
        "entity_type_normalized_count": le_stats["entity_type_normalized_count"],
        "negative_claim_count": int(kwargs["negative_claim_count"]),
        "local_resolver_ready": bool(
            le_stats["local_entity_count"] > 0
            or kwargs["local_cluster_count_meta"] > 0
            or (isinstance(local_resolver_trace, dict) and local_resolver_trace)
        ),
        "quality": quality_summary,
        "subject_context": {
            "context_subject_applied_count": int(subj_ctx_counters["applied"]),
            "context_subject_skipped_count": int(subj_ctx_counters["skipped"]),
            "context_subject_blocked_count": int(subj_ctx_counters["blocked"]),
            "context_subject_reset_count": int(subj_ctx_counters["reset"]),
            "context_subject_weak_subject_override_count": int(subj_ctx_counters["weak_subject_override"]),
        },
        "context_carryover_applied_count": int(subj_ctx_counters["applied"]),
        "context_carryover_blocked_count": int(subj_ctx_counters["blocked"]),
        "source_phrase_stripped_count": int(subj_ctx_counters["source_phrase_stripped"]),
        "subject_suffix_normalized_count": int(subj_ctx_counters["suffix_normalized"]),
        "carryover_missing_subject_error_count": int(subj_ctx_counters["missing_subject_error"]),
    }


__all__ = ["KnowledgeTracePayloadAssembler"]
