# backend/apps/knowledge/service/knowledge_trace_payload_builder.py
# Trace payload shaping helpers extracted from KnowledgeTraceService.

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.local_entity_cluster import local_entity_cluster_to_json_dict
from apps.knowledge.service.language_rules import fold_text, resolve_language
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1
from apps.knowledge.domain.technical_entity import technical_entity_to_json_dict
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1
from apps.knowledge.domain.technical_memory_chunk import technical_memory_chunk_to_json_dict
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1
from apps.knowledge.domain.search_profile import search_profile_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
from apps.knowledge.domain.candidate_selection import entity_candidate_to_json_dict
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.knowledge_trace_metrics import (
    bad_subject_claim_examples as _bad_subject_claim_examples,
    candidate_duplicate_removed_count as _candidate_duplicate_removed_count,
    candidate_evidence as _candidate_evidence,
    candidate_group_count as _candidate_group_count,
    candidate_has_evidence as _candidate_has_evidence,
    candidate_score as _candidate_score,
    candidate_selection_ready as _candidate_selection_ready,
    candidates_without_evidence_count as _candidates_without_evidence_count,
    canonical_entity_merge_suggestion_count as _canonical_entity_merge_suggestion_count,
    coerce_str_list as _coerce_str_list,
    conflict_count as _conflict_count,
    dedupe_candidate_selection_dicts as _dedupe_candidate_selection_dicts,
    dedupe_similarity_analysis_dicts as _dedupe_similarity_analysis_dicts,
    duplicate_memory_profile_count as _duplicate_memory_profile_count,
    hard_conflict_count as _hard_conflict_count,
    is_uuid_string as _is_uuid_string,
    multilingual_alias_match_count as _multilingual_alias_match_count,
    quality_summary_placeholder as _quality_summary_placeholder,
    reason_values as _reason_values,
    similarity_band_count as _similarity_band_count,
    similarity_boost_reason_count as _similarity_boost_reason_count,
    similarity_ready as _similarity_ready,
    similarity_score as _similarity_score,
    similarity_score_distribution as _similarity_score_distribution,
    similarity_without_evidence_count as _similarity_without_evidence_count,
    tension_band_count as _tension_band_count,
    tension_type_count as _tension_type_count,
    tension_without_evidence_count as _tension_without_evidence_count,
    top_candidate_score as _top_candidate_score,
    unknown_entity_type_examples as _unknown_entity_type_examples,
)
from apps.knowledge.service.knowledge_trace_view import (
    apply_trace_log_level as _apply_trace_log_level,
    attach_decisions_to_entity_rows as _attach_decisions_to_entity_rows,
    decision_entity_fields as _decision_entity_fields,
    global_profiles_from_dicts as _global_profiles_from_dicts,
    merge_events as _merge_events,
    normalize_trace_log_level as _normalize_trace_log_level,
    score_value as _score_value,
    sentences_without_claims as _sentences_without_claims,
    short_local_entity as _short_local_entity,
    top_candidates as _top_candidates,
    top_entities as _top_entities,
    top_problems as _top_problems,
)
from apps.knowledge.service.knowledge_trace_subject_context import *  # noqa: F401,F403

logger = logging.getLogger(__name__)

_LOW_COHERENCE_ENTITY_THRESHOLD = 0.7
_SENTENCE_INITIAL_TIME_VALUE_FOLD = {
    "korabban",
    "previously",
    "anteriormente",
    "jelenleg",
    "currently",
    "actualmente",
    "most",
}


def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
    message = str(exc).lower()
    return "does not exist" in message and table_name.lower() in message


def _lower_sentence_initial_time_value(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    folded = fold_text(value)
    if folded in _SENTENCE_INITIAL_TIME_VALUE_FOLD:
        return value[:1].lower() + value[1:]
    return value


def _fallback_space_time_frame_for_claim(claim: Any) -> dict[str, Any] | None:
    frame_id = getattr(claim, "space_time_frame_id", None)
    time_mode = getattr(claim, "time_mode", None) or "unknown"
    space_mode = getattr(claim, "space_mode", None) or "unknown"
    time_value = getattr(claim, "time_label", None)
    space_value = getattr(claim, "space_label", None)
    if not frame_id and time_mode == "unknown" and space_mode == "unknown" and not time_value and not space_value:
        return None
    return {
        "frame_id": frame_id or f"compat:{claim.claim_id}",
        "time_mode": time_mode,
        "time_value": _lower_sentence_initial_time_value(time_value),
        "time_start": None,
        "time_end": None,
        "time_precision": None,
        "time_confidence": float(getattr(claim, "confidence", 0.5) or 0.5),
        "space_mode": space_mode,
        "space_value": space_value,
        "space_precision": None,
        "space_confidence": float(getattr(claim, "confidence", 0.5) or 0.5),
        "overall_confidence": float(getattr(claim, "confidence", 0.5) or 0.5),
    }


def _uuid_or_none(value: Any) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _search_profile_from_dict(item: dict[str, Any]) -> SearchProfile:
    return SearchProfile(
        search_profile_id=_uuid_or_none(item.get("search_profile_id")) or UUID(int=0),
        run_id=_uuid_or_none(item.get("run_id")),
        source_id=_uuid_or_none(item.get("source_id")),
        technical_memory_chunk_id=_uuid_or_none(item.get("technical_memory_chunk_id")),
        technical_entity_id=_uuid_or_none(item.get("technical_entity_id")),
        local_entity_id=_uuid_or_none(item.get("local_entity_id")),
        entity_name=str(item.get("entity_name") or ""),
        entity_type=str(item.get("entity_type") or "unknown"),
        normalized_key=str(item.get("normalized_key") or ""),
        canonical_key=str(item.get("canonical_key") or item.get("normalized_key") or ""),
        canonical_text=str(item.get("canonical_text") or ""),
        search_text=str(item.get("search_text") or ""),
        aliases=[str(value) for value in item.get("aliases") or []],
        keywords=[str(value) for value in item.get("keywords") or []],
        claim_group_signals=dict(item.get("claim_group_signals") or {}),
        time_filters=dict(item.get("time_filters") or {}),
        space_filters=dict(item.get("space_filters") or {}),
        relation_filters=dict(item.get("relation_filters") or {}),
        evidence_refs=[dict(value) for value in item.get("evidence_refs") or [] if isinstance(value, dict)],
        builder_version=str(item.get("builder_version") or "search_profile_builder_v1"),
    )


def _timeline_compatibility_reasons(analyses: list[dict[str, Any]]) -> list[str]:
    return [
        reason
        for reason in _reason_values(analyses, "tension_reasons")
        if reason.startswith("temporal_change:")
    ]


def _near_duplicate_guard_trigger_count(
    decision_analyses: list[dict[str, Any]],
    local_resolver_trace: dict[str, Any] | None,
) -> int:
    decision_count = _decision_kind_count(decision_analyses, "keep_separate")
    resolver_count = 0
    if isinstance(local_resolver_trace, dict):
        for row in local_resolver_trace.get("entity_type_resolutions") or []:
            if isinstance(row, dict) and str(row.get("resolution") or "") == "conflict_split":
                resolver_count += 1
    return int(decision_count + resolver_count)


def _tension_ready(analyses: list[dict[str, Any]]) -> bool:
    return _tension_without_evidence_count(analyses) == 0


def _decision_kind_count(analyses: list[dict[str, Any]], *decisions: str) -> int:
    decision_set = set(decisions)
    return sum(1 for item in analyses if str(item.get("decision") or item.get("decision_type") or "") in decision_set)


def _decision_manual_review_count(analyses: list[dict[str, Any]]) -> int:
    return sum(1 for item in analyses if bool(item.get("manual_review_required")))


def _decision_ready(analyses: list[dict[str, Any]]) -> bool:
    """Decision réteg ready: minden döntés rendelkezik konzisztens decision string-gel és confidence-szel."""
    if not analyses:
        return True
    for item in analyses:
        if not str(item.get("decision") or "").strip():
            return False
    return True


def _global_profile_operation_count(profiles: list[dict[str, Any]], operation: str) -> int:
    return sum(1 for item in profiles if str(item.get("operation") or "") == operation)


def _global_profile_claim_count(profiles: list[dict[str, Any]], field: str) -> int:
    total = 0
    for item in profiles:
        try:
            total += int(item.get(field) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _affected_profile_ids(profiles: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in profiles:
        values = item.get("affected_profile_ids")
        candidates = values if isinstance(values, list) else [item.get("profile_id")]
        for value in candidates:
            text = str(value or "").strip()
            if text and text not in ids:
                ids.append(text)
    return ids


def _retrieval_conflicting_chunk_count(chunks: list[dict[str, Any]]) -> int:
    return sum(1 for item in chunks if bool(item.get("conflicting")))


def _retrieval_temporal_context_included(chunks: list[dict[str, Any]]) -> bool:
    return any(bool(item.get("temporal_context_included")) for item in chunks)


def _trace_claim_extraction_fields(claim: Any) -> dict[str, Any]:
    md = dict(getattr(claim, "metadata", None) or {})
    pat = md.get("pattern_name")
    sanitizers_applied = [str(item) for item in (md.get("sanitizers_applied") or []) if item]
    if md.get("context_subject_applied") is True:
        trace_subject_source = "carryover"
    elif sanitizers_applied:
        trace_subject_source = "sanitized"
    elif getattr(claim, "subject_text", None):
        trace_subject_source = "explicit"
    else:
        trace_subject_source = None
    out: dict[str, Any] = {
        "pattern": pat,
        "extraction_pattern": md.get("extraction_pattern") or pat,
        "extraction_language": md.get("extraction_language") or md.get("language"),
    }
    if trace_subject_source:
        out["subject_source"] = trace_subject_source
    subject_text = str(getattr(claim, "subject_text", "") or "").strip()
    if subject_text:
        out["subject_token_count"] = len(subject_text.split())
    if sanitizers_applied:
        out["sanitizers_applied"] = sanitizers_applied
    if md.get("context_subject_applied") is True and md.get("context_subject_source_sentence_id"):
        out["carryover_from_sentence_id"] = md.get("context_subject_source_sentence_id")
    for key in (
        "context_subject_applied",
        "context_subject_source_sentence_id",
        "context_subject_source_claim_id",
        "context_subject_source_subject",
        "context_subject_reason",
        "context_subject_sentence_pattern_id",
    ):
        if key in md:
            out[key] = md[key]
    return out




def _normalize_local_entity_trace_dict(raw: dict[str, Any]) -> dict[str, Any]:
    refs_in = raw.get("evidence_refs") or []
    evidence_refs: list[dict[str, Any]] = []
    if isinstance(refs_in, list):
        for ref in refs_in:
            if isinstance(ref, dict):
                evidence_refs.append(dict(ref))
    exp_raw = raw.get("explanation")
    explanation: dict[str, Any] = {}
    if isinstance(exp_raw, dict):
        explanation = dict(exp_raw)
        cf = explanation.get("coherence_factors")
        if isinstance(cf, list):
            explanation["coherence_factors"] = [str(x) for x in cf]
        else:
            explanation["coherence_factors"] = []
        explanation.setdefault("grouping_rule", "")
        explanation.setdefault("normalized_key", str(raw.get("normalized_key") or ""))
        explanation.setdefault("canonical_key", str(raw.get("canonical_key") or raw.get("normalized_key") or ""))
        explanation.setdefault("alias_match_reason", raw.get("alias_match_reason"))
        explanation.setdefault("entity_type_source", "")
        explanation.setdefault("claim_count", int(explanation.get("claim_count") or 0))
        explanation.setdefault("surface_form_count", int(explanation.get("surface_form_count") or 0))
    canonical_key = str(raw.get("canonical_key") or explanation.get("canonical_key") or raw.get("normalized_key") or "")
    alias_match_reason = raw.get("alias_match_reason")
    if alias_match_reason is None:
        alias_match_reason = explanation.get("alias_match_reason")
    return {
        "local_entity_id": str(raw.get("local_entity_id") or ""),
        "canonical_name": str(raw.get("canonical_name") or ""),
        "canonical_key": canonical_key,
        "entity_type": str(raw.get("entity_type") or "unknown"),
        "normalized_key": str(raw.get("normalized_key") or ""),
        "alias_match_reason": alias_match_reason,
        "confidence": float(raw.get("confidence") or 0.0),
        "coherence_score": float(raw.get("coherence_score") or 0.0),
        "surface_forms": _coerce_str_list_optional_strings(raw.get("surface_forms")),
        "mention_ids": _coerce_str_list(raw.get("mention_ids")),
        "claim_ids": _coerce_str_list(raw.get("claim_ids")),
        "sentence_ids": _coerce_str_list(raw.get("sentence_ids")),
        "evidence_refs": evidence_refs,
        "explanation": explanation,
    }


def _local_entity_summary_counts(entities: list[dict[str, Any]]) -> dict[str, int]:
    n = len(entities)
    low_coh = sum(1 for item in entities if float(item.get("coherence_score") or 0.0) < _LOW_COHERENCE_ENTITY_THRESHOLD)
    unknown_t = sum(1 for item in entities if str(item.get("entity_type") or "").lower() == "unknown")
    # Spec: entity_type_normalized_count = entity-k, ahol a típusinfer determinisztikusan
    # rátalált (mention_match vagy keyword) és a típus nem "unknown".
    normalized = 0
    for item in entities:
        entity_type = str(item.get("entity_type") or "").lower()
        if entity_type in {"", "unknown"}:
            continue
        explanation = item.get("explanation")
        if not isinstance(explanation, dict):
            continue
        source = str(explanation.get("entity_type_source") or "").lower()
        if source and source != "fallback":
            normalized += 1
    return {
        "local_entity_count": n,
        "low_coherence_local_entity_count": low_coh,
        "unknown_entity_type_count": unknown_t,
        "entity_type_normalized_count": normalized,
    }


def _claim_bucket_count(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    return len(value) if isinstance(value, list) else 0


def _technical_entity_trace_dict(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """Report-barát technical entity blokk, a nyers builder kimenetet megtartva."""
    time_sig = raw.get("time_signature") if isinstance(raw.get("time_signature"), dict) else {}
    space_sig = raw.get("space_signature") if isinstance(raw.get("space_signature"), dict) else {}
    evidence_refs = raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"), list) else []
    claim_groups = {
        "identity": _claim_bucket_count(raw, "identity_claims"),
        "descriptor": _claim_bucket_count(raw, "descriptor_claims"),
        "state": _claim_bucket_count(raw, "state_claims"),
        "relation": _claim_bucket_count(raw, "relation_claims"),
        "event": _claim_bucket_count(raw, "event_claims"),
        "rule": _claim_bucket_count(raw, "rule_claims"),
        "other": _claim_bucket_count(raw, "other_claims"),
    }
    out = dict(raw)
    out.update(
        {
            "index": index,
            "name": str(raw.get("canonical_name") or raw.get("name") or ""),
            "type": str(raw.get("entity_type") or raw.get("type") or "unknown"),
            "coherence": str(raw.get("coherence_state") or raw.get("coherence") or "unknown"),
            "claim_groups": claim_groups,
            "claims": dict(claim_groups),
            "time_signature_report": {
                "current": "yes" if bool(time_sig.get("has_current_claims")) else "no",
                "historical": "yes" if bool(time_sig.get("has_historical_claims")) else "no",
                "values": _coerce_str_list_optional_strings(time_sig.get("time_values")),
            },
            "space_signature_report": {
                "bounded": "yes" if bool(space_sig.get("has_bounded_space")) else "no",
                "values": _coerce_str_list_optional_strings(space_sig.get("space_values")),
            },
            "evidence": {
                "claims": sum(claim_groups.values())
                or len(evidence_refs),
            },
        }
    )
    return out



__all__ = [name for name in globals() if name.startswith("_") and not name.startswith("__")]
