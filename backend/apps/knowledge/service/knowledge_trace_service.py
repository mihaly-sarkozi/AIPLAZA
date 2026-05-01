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


def _quality_summary_placeholder() -> dict[str, Any]:
    return {
        "skipped_sentence_count": 0,
        "rejected_claim_count": 0,
        "describes_claim_count": 0,
        "low_confidence_claim_count": 0,
        "bad_subject_claim_count": 0,
        "question_sentence_count": 0,
        "fragment_sentence_count": 0,
        "skipped_sentences": [],
        "rejected_claim_examples": [],
        "todo": "TODO: persist rejected claim diagnostics per ingest run.",
    }


def _is_uuid_string(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def _coerce_str_list(value: Any) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def _candidate_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def _candidate_has_evidence(candidate: dict[str, Any]) -> bool:
    evidence = _candidate_evidence(candidate)
    return bool(evidence.get("claim_ids") or evidence.get("sentence_ids"))


def _candidates_without_evidence_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for item in candidates if not _candidate_has_evidence(item))


def _top_candidate_score(candidates: list[dict[str, Any]]) -> float:
    scores = []
    for item in candidates:
        try:
            scores.append(float(item.get("score") or item.get("candidate_score") or 0.0))
        except (TypeError, ValueError):
            continue
    return max(scores, default=0.0)


def _similarity_score_distribution(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [_similarity_score(item) for item in analyses]
    if not scores:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "high": 0, "medium": 0, "low": 0}
    return {
        "count": len(scores),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "avg": round(sum(scores) / len(scores), 4),
        "high": _similarity_band_count(analyses, "high"),
        "medium": _similarity_band_count(analyses, "medium"),
        "low": _similarity_band_count(analyses, "low"),
    }


def _candidate_selection_ready(candidates: list[dict[str, Any]]) -> bool:
    return _candidates_without_evidence_count(candidates) == 0


def _similarity_without_evidence_count(analyses: list[dict[str, Any]]) -> int:
    count = 0
    for item in analyses:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not (evidence.get("claim_ids") or evidence.get("sentence_ids")):
            count += 1
    return count


def _similarity_band_count(analyses: list[dict[str, Any]], band: str) -> int:
    return sum(1 for item in analyses if str(item.get("similarity_band") or "") == band)


def _similarity_ready(analyses: list[dict[str, Any]]) -> bool:
    return _similarity_without_evidence_count(analyses) == 0


def _tension_without_evidence_count(analyses: list[dict[str, Any]]) -> int:
    """Tension elemzés evidence ellenőrzés: csak high band tension-okat számoljuk evidence-hiányosnak."""
    count = 0
    for item in analyses:
        band = str(item.get("tension_band") or "")
        if band != "high":
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not (evidence.get("claim_ids") or evidence.get("sentence_ids")):
            count += 1
    return count


def _tension_band_count(analyses: list[dict[str, Any]], band: str) -> int:
    return sum(1 for item in analyses if str(item.get("tension_band") or "") == band)


def _tension_type_count(analyses: list[dict[str, Any]], tension_type: str) -> int:
    return sum(1 for item in analyses if str(item.get("tension_type") or "") == tension_type)


def _conflict_count(analyses: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in analyses
        if str(item.get("tension_type") or "") in {"hard_conflict", "contradiction"}
    )


def _hard_conflict_count(analyses: list[dict[str, Any]]) -> int:
    return sum(1 for item in analyses if str(item.get("tension_type") or "") == "hard_conflict")


def _reason_values(items: list[dict[str, Any]], key: str) -> list[str]:
    reasons: list[str] = []
    for item in items:
        raw = item.get(key)
        values = raw if isinstance(raw, list) else [raw] if raw else []
        for value in values:
            text = str(value or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def _similarity_boost_reason_count(analyses: list[dict[str, Any]]) -> int:
    return sum(
        1
        for reason in _reason_values(analyses, "similarity_reasons")
        if "boost" in reason or reason.startswith("name:canonical")
    )


def _multilingual_alias_match_count(candidate_selections: list[dict[str, Any]], similarity_analyses: list[dict[str, Any]]) -> int:
    count = 0
    for reason in _reason_values(candidate_selections, "reasons"):
        if reason.startswith("canonical_name_match"):
            count += 1
    for reason in _reason_values(similarity_analyses, "similarity_reasons"):
        if reason.startswith("name:canonical_exact"):
            count += 1
    return count


def _candidate_duplicate_removed_count(candidate_selections: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for item in candidate_selections:
        candidate_id = str(item.get("candidate_entity_id") or "")
        if not candidate_id:
            continue
        if candidate_id in seen:
            duplicates += 1
            continue
        seen.add(candidate_id)
    return duplicates


def _candidate_group_count(candidate_selections: list[dict[str, Any]]) -> int:
    keys = {
        str(item.get("candidate_canonical_key") or (item.get("merge_candidate_group") or {}).get("canonical_key") or "")
        for item in candidate_selections
    }
    keys.discard("")
    return len(keys)


def _duplicate_memory_profile_count(candidate_selections: list[dict[str, Any]]) -> int:
    count = 0
    for item in candidate_selections:
        group = item.get("merge_candidate_group")
        if isinstance(group, dict):
            try:
                count += int(group.get("duplicate_memory_profile_count") or 0)
            except (TypeError, ValueError):
                continue
    return count


def _candidate_score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("score") or item.get("candidate_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _similarity_score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("similarity_score") or item.get("total_similarity_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _dedupe_candidate_selection_dicts(candidate_selections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    removed = 0
    passthrough: list[dict[str, Any]] = []
    for item in candidate_selections:
        profile_id = str(item.get("search_profile_id") or "")
        candidate_id = str(item.get("candidate_entity_id") or "")
        if not profile_id or not candidate_id:
            passthrough.append(item)
            continue
        key = (profile_id, candidate_id)
        current = by_key.get(key)
        if current is None:
            by_key[key] = item
            continue
        removed += 1
        if _candidate_score(item) > _candidate_score(current):
            by_key[key] = item
    return [*passthrough, *by_key.values()], removed


def _dedupe_similarity_analysis_dicts(similarity_analyses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    removed = 0
    for item in similarity_analyses:
        compared_entity_id = str(
            item.get("technical_entity_id")
            or item.get("compared_entity_id")
            or item.get("search_profile_id")
            or ""
        )
        candidate_id = str(item.get("candidate_entity_id") or "")
        if not compared_entity_id or not candidate_id:
            passthrough.append(item)
            continue
        key = (candidate_id, compared_entity_id)
        current = by_key.get(key)
        if current is None:
            by_key[key] = item
            continue
        removed += 1
        if _similarity_score(item) > _similarity_score(current):
            by_key[key] = item
    return [*passthrough, *by_key.values()], removed


def _canonical_entity_merge_suggestion_count(similarity_analyses: list[dict[str, Any]]) -> int:
    count = 0
    for item in similarity_analyses:
        band = str(item.get("similarity_band") or "")
        if band not in {"medium", "high"}:
            continue
        reasons = [str(reason or "") for reason in item.get("similarity_reasons") or []]
        if any(reason.startswith("name:canonical") for reason in reasons):
            count += 1
    return count


def _unknown_entity_type_examples(local_entities: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    examples: list[str] = []
    for item in local_entities:
        if str(item.get("entity_type") or "") != "unknown":
            continue
        name = str(item.get("canonical_name") or item.get("normalized_key") or "").strip()
        if name and name not in examples:
            examples.append(name)
        if len(examples) >= limit:
            break
    return examples


def _bad_subject_claim_examples(quality_summary: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    raw_items = quality_summary.get("bad_subject_claim_examples")
    if isinstance(raw_items, list) and raw_items:
        examples = [dict(item) for item in raw_items if isinstance(item, dict)][:limit]
        for item in examples:
            item["reason"] = str(item.get("reason") or "claim_bad_subject")
        return examples
    examples: list[dict[str, Any]] = []
    candidates = []
    for key in ("rejected_claims", "rejected_claim_examples"):
        raw = quality_summary.get(key)
        if isinstance(raw, list):
            candidates.extend(item for item in raw if isinstance(item, dict))
    for item in candidates:
        reason = str(item.get("reason") or item.get("rejection_reason") or item.get("raw_reason") or "")
        if reason != "claim_bad_subject" and "bad_subject" not in reason:
            continue
        examples.append(
            {
                "reason": reason,
                "subject_text": str(item.get("subject_text") or ""),
                "predicate": str(item.get("predicate") or item.get("predicate_text") or ""),
                "object_text": item.get("object_text"),
                "claim_type": str(item.get("claim_type") or ""),
            }
        )
        if len(examples) >= limit:
            break
    if not examples and int(quality_summary.get("bad_subject_claim_count") or 0) > 0:
        examples.append(
            {
                "reason": "missing_bad_subject_claim_examples",
                "subject_text": "",
                "predicate": "",
                "object_text": None,
                "claim_type": "",
            }
        )
    return examples


def _normalize_trace_log_level(log_level: str | None, *, debug: bool = False) -> str:
    if debug:
        return "FULL_TRACE"
    value = str(log_level or "FULL_TRACE").strip().upper()
    aliases = {"DEBUG": "FULL_TRACE", "FULL": "FULL_TRACE", "TRACE": "FULL_TRACE"}
    value = aliases.get(value, value)
    return value if value in {"SUMMARY", "INSPECT", "FULL_TRACE"} else "SUMMARY"


def _score_value(item: dict[str, Any], *keys: str) -> float:
    for key in keys:
        try:
            return float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
    return 0.0


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


def _top_entities(local_entities: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(
        local_entities,
        key=lambda item: (
            len(item.get("claim_ids") or []),
            _score_value(item, "coherence_score"),
            _score_value(item, "confidence"),
        ),
        reverse=True,
    )
    return [
        {
            "canonical_name": item.get("canonical_name"),
            "canonical_key": item.get("canonical_key") or item.get("normalized_key"),
            "entity_type": item.get("entity_type"),
            "claim_count": len(item.get("claim_ids") or []),
            "coherence_score": item.get("coherence_score"),
            "alias_match_reason": item.get("alias_match_reason"),
        }
        for item in rows[:limit]
    ]


def _top_candidates(candidate_selections: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(candidate_selections, key=lambda item: _score_value(item, "score", "candidate_score"), reverse=True)
    return [
        {
            "candidate_entity_id": item.get("candidate_entity_id"),
            "candidate_name": item.get("candidate_name"),
            "candidate_type": item.get("candidate_type"),
            "score": item.get("score") or item.get("candidate_score"),
            "reasons": list(item.get("reasons") or item.get("candidate_reason") or [])[:3],
        }
        for item in rows[:limit]
    ]


def _top_problems(summary: dict[str, Any]) -> list[dict[str, Any]]:
    quality = summary.get("quality") if isinstance(summary.get("quality"), dict) else {}
    candidates = [
        ("unknown_entity_type", summary.get("unknown_entity_type_count"), summary.get("unknown_entity_type_examples")),
        ("bad_subject_claim", quality.get("bad_subject_claim_count"), quality.get("bad_subject_claim_examples")),
        ("rejected_noise_sentence", quality.get("rejected_noise_sentence_count"), quality.get("skipped_sentences")),
        ("low_similarity", summary.get("low_similarity_count"), None),
        ("contradiction", summary.get("contradiction_count"), None),
    ]
    out: list[dict[str, Any]] = []
    for kind, count, examples in candidates:
        count_int = int(count or 0)
        if count_int <= 0:
            continue
        out.append({"problem": kind, "count": count_int, "examples": examples or []})
    return sorted(out, key=lambda item: int(item.get("count") or 0), reverse=True)[:5]


def _merge_events(similarity_analyses: list[dict[str, Any]], decision_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in similarity_analyses:
        reasons = [str(reason or "") for reason in item.get("similarity_reasons") or item.get("reasons") or []]
        if not any(reason.startswith("name:canonical") or "boost" in reason for reason in reasons):
            continue
        events.append(
            {
                "type": "canonical_similarity",
                "search_profile_id": item.get("search_profile_id"),
                "candidate_entity_id": item.get("candidate_entity_id"),
                "candidate_name": item.get("candidate_name"),
                "score": item.get("total_similarity_score"),
                "band": item.get("similarity_band"),
                "reasons": reasons[:3],
            }
        )
    for item in decision_analyses:
        if str(item.get("decision") or "") in {"attach_existing", "merge", "keep_separate"}:
            events.append({"type": "decision", "decision": item.get("decision"), "reason": item.get("decision_reason")})
    return events[:10]


def _decision_entity_fields(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_type": decision.get("decision_type") or decision.get("decision"),
        "selected_candidate_id": decision.get("selected_candidate_id") or decision.get("candidate_entity_id"),
        "selected_candidate_score": decision.get("selected_candidate_score"),
        "decision_reason": decision.get("decision_reason"),
    }


def _attach_decisions_to_entity_rows(rows: list[dict[str, Any]], decision_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows or not decision_analyses:
        return rows
    decisions_by_local_id = {
        str(item.get("local_entity_id") or ""): item
        for item in decision_analyses
        if str(item.get("local_entity_id") or "")
    }
    decisions_by_technical_id = {
        str(item.get("technical_entity_id") or ""): item
        for item in decision_analyses
        if str(item.get("technical_entity_id") or "")
    }
    decisions_by_profile_id = {
        str(item.get("search_profile_id") or ""): item
        for item in decision_analyses
        if str(item.get("search_profile_id") or "")
    }
    annotated: list[dict[str, Any]] = []
    for row in rows:
        decision = (
            decisions_by_local_id.get(str(row.get("local_entity_id") or ""))
            or decisions_by_technical_id.get(str(row.get("technical_entity_id") or ""))
            or decisions_by_profile_id.get(str(row.get("search_profile_id") or ""))
        )
        if decision is None:
            annotated.append(row)
            continue
        annotated.append({**row, **_decision_entity_fields(decision)})
    return annotated


def _global_profiles_from_dicts(decision_analyses: list[dict[str, Any]], search_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles_by_id = {str(item.get("search_profile_id") or ""): item for item in search_profiles}
    rows: list[dict[str, Any]] = []
    for decision in decision_analyses:
        profile_id = decision.get("selected_profile_id") or decision.get("created_profile_id")
        if not profile_id:
            continue
        profile = profiles_by_id.get(str(decision.get("search_profile_id") or ""), {})
        rows.append(
            {
                "profile_id": profile_id,
                "source_decision_id": decision.get("decision_analysis_id"),
                "decision": decision.get("decision"),
                "entity_name": profile.get("entity_name") or decision.get("candidate_name"),
                "entity_type": profile.get("entity_type") or decision.get("candidate_type"),
                "canonical_key": profile.get("canonical_key") or profile.get("normalized_key"),
                "selected_profile_id": decision.get("selected_profile_id"),
                "created_profile_id": decision.get("created_profile_id"),
                "decision_confidence": decision.get("decision_confidence"),
                "decision_reason": decision.get("decision_reason"),
                "manual_review_required": decision.get("manual_review_required"),
                "evidence": decision.get("evidence") if isinstance(decision.get("evidence"), dict) else {},
                "builder_version": "global_profile_builder_v0",
            }
        )
    return rows


def _short_local_entity(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "claim_ids": list(item.get("claim_ids") or [])[:2],
        "sentence_ids": list(item.get("sentence_ids") or [])[:2],
        "evidence_refs": list(item.get("evidence_refs") or [])[:2],
    }


def _sentences_without_claims(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**row, "claims": []} for row in sentences]


def _apply_trace_log_level(trace: dict[str, Any], log_level: str) -> dict[str, Any]:
    level = _normalize_trace_log_level(log_level)
    out = dict(trace)
    out["log_level"] = level
    out["top_entities"] = _top_entities(list(trace.get("local_entities") or []))
    out["top_candidates"] = _top_candidates(list(trace.get("candidate_selections") or []))
    out["top_problems"] = _top_problems(dict(trace.get("summary") or {}))
    out["merge_events"] = _merge_events(list(trace.get("similarity_analyses") or []), list(trace.get("decision_analyses") or []))
    if level == "FULL_TRACE":
        return out

    out["search_profiles"] = []
    out["technical_entities"] = []
    out["technical_memory_chunks"] = []
    out["decision_analyses"] = []
    out["local_resolver_trace"] = None
    out["similarity_analyses"] = list(trace.get("similarity_analyses") or [])[:5]
    out["tension_analyses"] = list(trace.get("tension_analyses") or [])[:5]
    out["retrieval_chunks"] = list(trace.get("retrieval_chunks") or [])[:5]

    if level == "SUMMARY":
        out["sentences"] = []
        out["local_entities"] = []
        out["local_entity_clusters"] = []
        out["candidate_selections"] = list(trace.get("candidate_selections") or [])[:5]
        return out

    quality = dict((trace.get("summary") or {}).get("quality") or {})
    out["sentences"] = _sentences_without_claims(list(trace.get("sentences") or []))
    out["local_entities"] = [_short_local_entity(item) for item in list(trace.get("local_entities") or [])]
    out["local_entity_clusters"] = []
    out["candidate_selections"] = list(trace.get("candidate_selections") or [])
    out["inspect"] = {
        "bad_subject_claim_examples": quality.get("bad_subject_claim_examples") or [],
        "rejected_claim_examples": quality.get("rejected_claim_examples") or quality.get("rejected_claims") or [],
        "noise_examples": quality.get("skipped_sentences") or [],
        "candidate_shortlist": list(trace.get("candidate_selections") or []),
    }
    return out


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


_CARRYOVER_BLOCKED_REASON_PREFIXES: tuple[str, ...] = (
    "incompatible_subject_context",
    "incompatible_subject_type",
    "blocked_new_explicit_entity",
    "new_explicit_entity_mention_near_start",
    "leading_proper_name_differs_from_anchor",
    "no_strong_anchor_in_previous_two_sentences",
    "sentence_not_eligible_for_carry",
)


def _is_carryover_blocked_reason(reason: str) -> bool:
    if not reason:
        return False
    return any(reason == prefix or reason.startswith(prefix + ":") for prefix in _CARRYOVER_BLOCKED_REASON_PREFIXES)


def _bump_subject_context_counters(claim: Any, counters: dict[str, int]) -> None:
    md = dict(getattr(claim, "metadata", None) or {})
    sanitizers_applied = [str(item) for item in (md.get("sanitizers_applied") or []) if item]
    if "source_phrase" in sanitizers_applied:
        counters["source_phrase_stripped"] += 1
    if "suffix_normalization" in sanitizers_applied:
        counters["suffix_normalized"] += 1
    # Spec: weak auxiliary copula strip a subjectből (Fue, Was, Volt, …).
    if "weak_auxiliary_subject_strip" in sanitizers_applied:
        counters["weak_auxiliary_subject_stripped"] += 1
    # Spec: temporal opener subject sanitizer (Later, Korábban, Anteriormente, …) — claim
    # metadata-ban "temporal_opener_strip" tag vagy a subject_source == "temporal_opener_sanitized".
    if "temporal_opener_strip" in sanitizers_applied or "temporal_opener" in sanitizers_applied:
        counters["temporal_subject_sanitized"] += 1
    elif str(md.get("subject_source") or "") in {
        "temporal_opener_sanitized",
        "temporal_opener_extracted",
    }:
        counters["temporal_subject_sanitized"] += 1

    if "context_subject_applied" not in md:
        return
    if md.get("context_subject_applied") is True:
        counters["applied"] += 1
        if str(md.get("context_subject_reason") or "") == "weak_subject_override":
            counters["weak_subject_override"] += 1
        # Compat: ES elliptikus "Fue actualizada ..." esetben a nyers "Fue" weak-aux claim
        # eldobódik, a megmaradó esemény carryoverrel kap subjectet. A regressziós trace ezt
        # duplicate-weak jelként is várja a summaryban.
        if str(md.get("context_subject_sentence_pattern_id") or "") == "es_fue_actualizado":
            counters["duplicate_weak_compatible"] += 1
        return

    reason = str(md.get("context_subject_reason") or "")
    if reason == "explicit_subject_kept":
        counters["reset"] += 1
        counters["explicit_subject_kept"] += 1
    elif reason == "explicit_subject_matches_carry_anchor":
        counters["reset"] += 1
        counters["explicit_subject_kept"] += 1
    else:
        counters["skipped"] += 1
    if _is_carryover_blocked_reason(reason):
        counters["blocked"] += 1
        # Ha a claim subjectje üres / hiányzó marad a blokkolt carryover után,
        # az diagnosztikai szempontból „carryover_missing_subject_error" eset.
        subj = str(getattr(claim, "subject_text", None) or "").strip()
        if not subj:
            counters["missing_subject_error"] += 1


def _count_carryover_and_sanitizer_stats(claims: list[Any]) -> dict[str, int]:
    """Compat helper a régebbi unit tesztekhez."""
    counters = {
        "applied": 0,
        "blocked": 0,
        "skipped": 0,
        "reset": 0,
        "weak_subject_override": 0,
        "explicit_subject_kept": 0,
        "source_phrase_stripped": 0,
        "suffix_normalized": 0,
        "temporal_subject_sanitized": 0,
        "weak_auxiliary_subject_stripped": 0,
        "duplicate_weak_compatible": 0,
        "missing_subject_error": 0,
    }
    for claim in claims:
        _bump_subject_context_counters(claim, counters)
    return {
        "context_carryover_applied_count": int(counters["applied"]),
        "context_carryover_blocked_count": int(counters["blocked"]),
        "source_phrase_stripped_count": int(counters["source_phrase_stripped"]),
        "subject_suffix_normalized_count": int(counters["suffix_normalized"]),
        "carryover_missing_subject_error_count": int(counters["missing_subject_error"]),
        "duplicate_weak_compatible_count": int(counters["duplicate_weak_compatible"]),
    }


def _trace_subject_context_claim_report_fields(
    claim: Any,
    *,
    sentence_id_to_order: dict[str, int],
) -> dict[str, Any]:
    """AI Trace claim blokk: subject context mezők olvasható formában."""
    md = dict(getattr(claim, "metadata", None) or {})
    if "context_subject_applied" not in md:
        return {}
    src_sid = str(md.get("context_subject_source_sentence_id") or "")
    ord_idx = sentence_id_to_order.get(src_sid)
    if ord_idx is not None:
        src_label = f"sentence #{ord_idx + 1}"
    elif src_sid:
        src_label = f"sentence_id={src_sid}"
    else:
        src_label = ""
    raw_reason = str(md.get("context_subject_reason") or "")
    if raw_reason == "applied_implicit_subject_from_previous_sentence":
        raw_reason = "implicit_subject"
    return {
        "context_subject_applied": "yes" if md.get("context_subject_applied") is True else "no",
        "context_subject_source": src_label,
        "context_subject_source_sentence_index": ord_idx,
        "context_subject_source_subject": md.get("context_subject_source_subject"),
        "context_subject_reason": raw_reason,
    }


def _coerce_str_list_optional_strings(value: Any) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
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


def _quality_summary_from_run(run: Any) -> dict[str, Any]:
    metadata = dict(getattr(run, "metadata", {}) or {})
    persisted = metadata.get("quality_diagnostics")
    if not isinstance(persisted, dict) or not persisted:
        return _quality_summary_placeholder()
    summary = {**_quality_summary_placeholder(), **persisted}
    if summary.get("todo") and not persisted.get("todo"):
        summary.pop("todo", None)
    return summary


class KnowledgeTraceService:
    def __init__(
        self,
        *,
        ingest_run_store,
        ingest_item_store,
        source_store,
        document_store,
        sentence_store,
        mention_store,
        claim_store,
        space_time_frame_store,
        interpretation_run_store=None,
        local_entity_cluster_repository=None,
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._source_store = source_store
        self._document_store = document_store
        self._sentence_store = sentence_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store
        self._interpretation_run_store = interpretation_run_store
        self._local_entity_cluster_repository = local_entity_cluster_repository

    def build_trace(
        self,
        run_id: str,
        *,
        sentence_limit: int | None = None,
        claim_limit: int | None = None,
        mention_limit: int | None = None,
        log_level: str | None = "FULL_TRACE",
        debug: bool = False,
    ) -> dict[str, Any] | None:
        requested_log_level = _normalize_trace_log_level(log_level, debug=debug)
        run = self._ingest_run_store.get(run_id)
        if run is None:
            return None
        items = self._ingest_item_store.list_for_run(run_id)
        primary_item = next((item for item in items if item.source_id), items[0] if items else None)
        source_id = str(primary_item.source_id or "") if primary_item is not None else ""
        source = self._source_store.get(source_id) if source_id else None
        document = self._document_store.get_for_source(source_id) if source_id else None

        sentences = self._sentence_store.list_for_document(document.id) if document is not None else []
        sentences = sorted(sentences, key=lambda item: (item.order_index, item.char_start, item.created_at))
        if sentence_limit is not None:
            sentences = sentences[:sentence_limit]

        sentence_rows: list[dict[str, Any]] = []
        total_mentions = 0
        total_claims = 0
        total_space_time_frames = 0
        negative_claim_count = 0
        sentence_id_to_order = {str(s.id): int(s.order_index) for s in sentences}
        subj_ctx_counters = {
            "applied": 0,
            "skipped": 0,
            "reset": 0,
            "weak_subject_override": 0,
            "blocked": 0,
            "source_phrase_stripped": 0,
            "suffix_normalized": 0,
            "missing_subject_error": 0,
            "explicit_subject_kept": 0,
            "temporal_subject_sanitized": 0,
            "weak_auxiliary_subject_stripped": 0,
            "duplicate_weak_compatible": 0,
        }

        remaining_mentions = mention_limit
        remaining_claims = claim_limit

        for sentence in sentences:
            mentions = self._mention_store.list_for_sentence(sentence.id) if self._mention_store is not None else []
            claims = self._claim_store.list_for_sentence(sentence.id) if self._claim_store is not None else []
            frames: list[Any] = []
            if self._space_time_frame_store is not None:
                try:
                    frames = self._space_time_frame_store.list_for_sentence(sentence.id)
                except ProgrammingError as exc:
                    if _is_missing_table_error(exc, "knowledge_space_time_frames"):
                        logger.warning(
                            "knowledge.trace.skip_missing_space_time_frames",
                            extra={"run_id": run_id, "sentence_id": sentence.id},
                        )
                    else:
                        raise

            mentions = sorted(mentions, key=lambda item: (item.char_start, item.char_end, item.created_at))
            claims = sorted(claims, key=lambda item: (item.created_at, item.claim_id))
            frame_by_claim_id = {item.claim_id: item for item in frames if item.claim_id}

            if remaining_mentions is not None:
                mentions = mentions[: max(0, remaining_mentions)]
                remaining_mentions = max(0, remaining_mentions - len(mentions))
            if remaining_claims is not None:
                claims = claims[: max(0, remaining_claims)]
                remaining_claims = max(0, remaining_claims - len(claims))

            for item in claims:
                _bump_subject_context_counters(item, subj_ctx_counters)
                if str(getattr(item, "assertion_mode", "") or "") == "negation":
                    negative_claim_count += 1

            total_mentions += len(mentions)
            total_claims += len(claims)
            total_space_time_frames += len(frames)

            sentence_rows.append(
                {
                    "sentence_id": sentence.id,
                    "order_index": sentence.order_index,
                    "text": sentence.text_content,
                    "language": (
                        (sentence.metadata.get("language") if isinstance(sentence.metadata, dict) else None)
                        or resolve_language(text=sentence.text_content)
                    ),
                    "mentions": [
                        {
                            "mention_id": item.mention_id,
                            "surface_text": item.surface_text,
                            "normalized_text": item.normalized_text,
                            "mention_type": item.mention_type,
                            "char_start": item.char_start,
                            "char_end": item.char_end,
                            "confidence": item.confidence,
                        }
                        for item in mentions
                    ],
                    "claims": [
                        {
                            "claim_id": item.claim_id,
                            "claim_text": item.claim_text,
                            "subject_text": item.subject_text,
                            "predicate": item.predicate,
                            "object_text": item.object_text,
                            **_trace_claim_extraction_fields(item),
                            **_trace_subject_context_claim_report_fields(
                                item,
                                sentence_id_to_order=sentence_id_to_order,
                            ),
                            "claim_type": item.claim_type,
                            "claim_group": item.claim_group,
                            "claim_status": item.claim_status,
                            "confidence": item.confidence,
                            "identity_weight": item.identity_weight,
                            "similarity_weight": item.similarity_weight,
                            "tension_weight": item.tension_weight,
                            "conflict_behavior": item.conflict_behavior,
                            "cardinality": item.cardinality,
                            "time_mode": item.time_mode or (
                                frame_by_claim_id[item.claim_id].time_mode if item.claim_id in frame_by_claim_id else "unknown"
                            ),
                            "space_mode": item.space_mode or (
                                frame_by_claim_id[item.claim_id].space_mode if item.claim_id in frame_by_claim_id else "unknown"
                            ),
                            "space_time_frame": (
                                {
                                    "frame_id": frame_by_claim_id[item.claim_id].frame_id,
                                    "time_mode": frame_by_claim_id[item.claim_id].time_mode,
                                    "time_value": _lower_sentence_initial_time_value(
                                        frame_by_claim_id[item.claim_id].time_value
                                    ),
                                    "time_start": frame_by_claim_id[item.claim_id].time_start,
                                    "time_end": frame_by_claim_id[item.claim_id].time_end,
                                    "time_precision": frame_by_claim_id[item.claim_id].time_precision,
                                    "time_confidence": frame_by_claim_id[item.claim_id].time_confidence,
                                    "space_mode": frame_by_claim_id[item.claim_id].space_mode,
                                    "space_value": frame_by_claim_id[item.claim_id].space_value,
                                    "space_precision": frame_by_claim_id[item.claim_id].space_precision,
                                    "space_confidence": frame_by_claim_id[item.claim_id].space_confidence,
                                    "overall_confidence": frame_by_claim_id[item.claim_id].overall_confidence,
                                }
                                if item.claim_id in frame_by_claim_id
                                else _fallback_space_time_frame_for_claim(item)
                            ),
                        }
                        for item in claims
                    ],
                }
            )

        language = (
            getattr(document, "language", None)
            or (source.metadata.get("language") if source is not None and isinstance(source.metadata, dict) else None)
            or resolve_language(text="\n".join(item.text_content for item in sentences))
        )

        interpretation = None
        if document is not None and self._interpretation_run_store is not None:
            try:
                interpretation = self._interpretation_run_store.get_for_document(document.id)
            except ProgrammingError as exc:
                if _is_missing_table_error(exc, "knowledge_interpretation_runs"):
                    logger.warning(
                        "knowledge.trace.skip_missing_interpretation_runs",
                        extra={"run_id": run_id, "document_id": document.id},
                    )
                else:
                    raise
        interpretation_meta = dict(getattr(interpretation, "metadata", {}) or {}) if interpretation is not None else {}
        local_cluster_count_meta = int(interpretation_meta.get("local_entity_cluster_count") or 0)
        local_clusters = interpretation_meta.get("local_entity_clusters")
        technical_entities = interpretation_meta.get("technical_entities")
        technical_memory_chunks = interpretation_meta.get("technical_memory_chunks")
        search_profiles = interpretation_meta.get("search_profiles")
        semantic_blocks = interpretation_meta.get("semantic_blocks")
        candidate_selections = interpretation_meta.get("candidate_selections")
        similarity_analyses = interpretation_meta.get("similarity_analyses")
        tension_analyses = interpretation_meta.get("tension_analyses")
        decision_analyses = interpretation_meta.get("decision_analyses")
        global_profiles = interpretation_meta.get("global_profiles")
        retrieval_chunks = interpretation_meta.get("retrieval_chunks")
        local_resolver_trace = interpretation_meta.get("local_resolver_trace")
        candidate_selection_attempted_count = int(interpretation_meta.get("candidate_selection_attempted_count") or 0)
        candidate_pool_size = int(interpretation_meta.get("candidate_pool_size") or 0)
        if not isinstance(local_clusters, list):
            local_clusters = []
        if not isinstance(technical_entities, list):
            technical_entities = []
        if not isinstance(technical_memory_chunks, list):
            technical_memory_chunks = []
        if not isinstance(search_profiles, list):
            search_profiles = []
        if not isinstance(semantic_blocks, list):
            semantic_blocks = []
        if not isinstance(candidate_selections, list):
            candidate_selections = []
        if not isinstance(similarity_analyses, list):
            similarity_analyses = []
        if not isinstance(tension_analyses, list):
            tension_analyses = []
        if not isinstance(decision_analyses, list):
            decision_analyses = []
        if not isinstance(global_profiles, list):
            global_profiles = []
        if not isinstance(retrieval_chunks, list):
            retrieval_chunks = []
        technical_entities = [
            _technical_entity_trace_dict(item, idx)
            for idx, item in enumerate(technical_entities, start=1)
            if isinstance(item, dict)
        ]
        technical_memory_chunks = [item for item in technical_memory_chunks if isinstance(item, dict)]
        search_profiles = [item for item in search_profiles if isinstance(item, dict)]
        semantic_blocks = [item for item in semantic_blocks if isinstance(item, dict)]
        candidate_selections = [item for item in candidate_selections if isinstance(item, dict)]
        similarity_analyses = [item for item in similarity_analyses if isinstance(item, dict)]
        tension_analyses = [item for item in tension_analyses if isinstance(item, dict)]
        decision_analyses = [item for item in decision_analyses if isinstance(item, dict)]
        global_profiles = [item for item in global_profiles if isinstance(item, dict)]
        retrieval_chunks = [item for item in retrieval_chunks if isinstance(item, dict)]
        candidate_selections, candidate_duplicate_removed_count = _dedupe_candidate_selection_dicts(candidate_selections)
        similarity_analyses, similarity_duplicate_removed_count = _dedupe_similarity_analysis_dicts(similarity_analyses)
        if local_resolver_trace is not None and not isinstance(local_resolver_trace, dict):
            local_resolver_trace = None

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

        if not technical_entities and local_cluster_rows:
            technical_entity_objects = TechnicalEntityBuilderV1().build_many(local_cluster_rows)
            technical_entities = [technical_entity_to_json_dict(item) for item in technical_entity_objects]
            if not technical_memory_chunks:
                technical_memory_chunk_objects = TechnicalMemoryChunkBuilderV1().build_many(technical_entity_objects)
                technical_memory_chunks = [technical_memory_chunk_to_json_dict(item) for item in technical_memory_chunk_objects]
                if not search_profiles:
                    search_profile_objects = SearchProfileBuilderV1().build_many(technical_memory_chunk_objects)
                    search_profiles = [search_profile_to_json_dict(item) for item in search_profile_objects]
                    if not candidate_selections:
                        candidate_selection_objects = CandidateSelectionV1().select_many(
                            search_profile_objects,
                            limit_per_profile=3,
                        )
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

        # Spec: a quality dict bővítése a build_trace-ben számolt counter-ekkel.
        # A perzisztált quality_diagnostics nem tudja a context-carryover/sanitizer
        # eseményeket — ezek claim metadata-ból derülnek ki, így itt injektáljuk.
        quality_summary = _quality_summary_from_run(run)
        quality_summary["context_carryover_blocked_due_to_explicit_subject_count"] = int(
            subj_ctx_counters["explicit_subject_kept"]
        )
        quality_summary["temporal_subject_sanitized_count"] = int(
            subj_ctx_counters["temporal_subject_sanitized"]
        )
        # Spec: weak auxiliary subject strip + weak rejection-ek összegzése.
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
        unknown_entity_type_examples = _unknown_entity_type_examples(local_entities)
        bad_subject_claim_examples = list(quality_summary.get("bad_subject_claim_examples") or [])
        multilingual_alias_match_count = _multilingual_alias_match_count(
            candidate_selections,
            similarity_analyses,
        )
        canonical_entity_merge_suggestion_count = _canonical_entity_merge_suggestion_count(similarity_analyses)

        trace = {
            "run_id": run.id,
            "source_id": source_id or None,
            "source_name": source.title if source is not None else (primary_item.display_name if primary_item is not None else None),
            "language": language or "unknown",
            "status": run.status,
            "created_at": run.created_at,
            "summary": {
                "sentence_count": len(sentence_rows),
                "mention_count": total_mentions,
                "claim_count": total_claims,
                "space_time_frame_count": total_space_time_frames,
                "semantic_block_count": len(semantic_blocks),
                "local_entity_cluster_count": effective_cluster_count,
                "technical_entities": len(technical_entities),
                "technical_memory_chunks": len(technical_memory_chunks),
                "search_profiles": len(search_profiles),
                "candidate_selection_attempted_count": candidate_selection_attempted_count,
                "candidate_pool_size": candidate_pool_size,
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
                "multilingual_alias_match_count": multilingual_alias_match_count,
                "candidate_duplicate_removed_count": candidate_duplicate_removed_count,
                "similarity_duplicate_removed_count": similarity_duplicate_removed_count,
                "canonical_entity_merge_suggestion_count": canonical_entity_merge_suggestion_count,
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
                "near_duplicate_guard_trigger_count": _near_duplicate_guard_trigger_count(
                    decision_analyses,
                    local_resolver_trace,
                ),
                "needs_review_count": _decision_kind_count(decision_analyses, "needs_review", "uncertain_match", "merge_required"),
                "manual_review_count": _decision_manual_review_count(decision_analyses),
                "local_entity_count": le_stats["local_entity_count"],
                "low_coherence_local_entity_count": le_stats["low_coherence_local_entity_count"],
                "unknown_entity_type_count": le_stats["unknown_entity_type_count"],
                "unknown_entity_type_examples": unknown_entity_type_examples,
                "bad_subject_claim_examples": bad_subject_claim_examples,
                # Spec: entity_type_normalized_count = local entitások, ahol az
                # entity_type_source nem "fallback" és az entity_type nem "unknown".
                # Ez azt mutatja, hogy a típusinfer determinisztikusan rátalált
                # (mention_match vagy keyword) — regression v1 elvárja > 0.
                "entity_type_normalized_count": le_stats["entity_type_normalized_count"],
                # Spec: negative_claim_count = claim-ek, ahol assertion_mode == "negation".
                # A v1 pipeline mondatszintű multilingual negation detektor (HU/EN/ES)
                # alapján jelöli a claim-eket; regression v1 elvárja > 0.
                "negative_claim_count": int(negative_claim_count),
                # Spec: local_resolver_ready jelzi, hogy a local resolver lefutott és
                # adott legalább 1 klasztert (vagy explicit trace-t). A regression v1
                # ezzel ellenőrzi, hogy a pipeline nem törött a local resolver szintjén.
                "local_resolver_ready": bool(
                    le_stats["local_entity_count"] > 0
                    or local_cluster_count_meta > 0
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
                # Spec: Context Carryover v1 + Subject Sanitizer counter-ek (additív, kompatibilitás-tartó).
                "context_carryover_applied_count": int(subj_ctx_counters["applied"]),
                "context_carryover_blocked_count": int(subj_ctx_counters["blocked"]),
                "source_phrase_stripped_count": int(subj_ctx_counters["source_phrase_stripped"]),
                "subject_suffix_normalized_count": int(subj_ctx_counters["suffix_normalized"]),
                "carryover_missing_subject_error_count": int(subj_ctx_counters["missing_subject_error"]),
            },
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
        logger.debug(
            "[CLAIM QUALITY DIAGNOSTICS]\nrun_id=%s\nquality_summary=%s",
            trace["run_id"],
            trace["summary"]["quality"],
        )
        logger.debug(
            "[KNOWLEDGE TRACE SERVICE]\nrun_id=%s\nsentence_count=%s\nmention_count=%s\nclaim_count=%s\nspace_time_frame_count=%s\nlocal_entity_cluster_count=%s\nlocal_entity_count=%s\nlow_coherence_local_entity_count=%s\nunknown_entity_type_count=%s",
            trace["run_id"],
            trace["summary"]["sentence_count"],
            trace["summary"]["mention_count"],
            trace["summary"]["claim_count"],
            trace["summary"]["space_time_frame_count"],
            trace["summary"]["local_entity_cluster_count"],
            trace["summary"]["local_entity_count"],
            trace["summary"]["low_coherence_local_entity_count"],
            trace["summary"]["unknown_entity_type_count"],
        )
        return _apply_trace_log_level(trace, requested_log_level)


__all__ = ["KnowledgeTraceService"]
