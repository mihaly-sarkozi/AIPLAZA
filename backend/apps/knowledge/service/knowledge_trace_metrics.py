# backend/apps/knowledge/service/knowledge_trace_metrics.py
# Feladat: Knowledge trace diagnosztikai mérőszámokat és deduplikációs helper függvényeket tartalmaz. Candidate selection, similarity, tension, decision és quality summary számításokat választ le a KnowledgeTraceService fájlról. Program-specifikus trace/observability utility réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any
from uuid import UUID


def quality_summary_placeholder() -> dict[str, Any]:
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


def is_uuid_string(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def coerce_str_list(value: Any) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def candidate_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def candidate_has_evidence(candidate: dict[str, Any]) -> bool:
    evidence = candidate_evidence(candidate)
    return bool(evidence.get("claim_ids") or evidence.get("sentence_ids"))


def candidates_without_evidence_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for item in candidates if not candidate_has_evidence(item))


def top_candidate_score(candidates: list[dict[str, Any]]) -> float:
    scores = []
    for item in candidates:
        try:
            scores.append(float(item.get("score") or item.get("candidate_score") or 0.0))
        except (TypeError, ValueError):
            continue
    return max(scores, default=0.0)


def candidate_selection_ready(candidates: list[dict[str, Any]]) -> bool:
    return candidates_without_evidence_count(candidates) == 0


def similarity_score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("similarity_score") or item.get("total_similarity_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def similarity_band_count(analyses: list[dict[str, Any]], band: str) -> int:
    return sum(1 for item in analyses if str(item.get("similarity_band") or "") == band)


def similarity_score_distribution(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [similarity_score(item) for item in analyses]
    if not scores:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "high": 0, "medium": 0, "low": 0}
    return {
        "count": len(scores),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "avg": round(sum(scores) / len(scores), 4),
        "high": similarity_band_count(analyses, "high"),
        "medium": similarity_band_count(analyses, "medium"),
        "low": similarity_band_count(analyses, "low"),
    }


def similarity_without_evidence_count(analyses: list[dict[str, Any]]) -> int:
    count = 0
    for item in analyses:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not (evidence.get("claim_ids") or evidence.get("sentence_ids")):
            count += 1
    return count


def similarity_ready(analyses: list[dict[str, Any]]) -> bool:
    return similarity_without_evidence_count(analyses) == 0


def tension_without_evidence_count(analyses: list[dict[str, Any]]) -> int:
    count = 0
    for item in analyses:
        band = str(item.get("tension_band") or "")
        if band != "high":
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not (evidence.get("claim_ids") or evidence.get("sentence_ids")):
            count += 1
    return count


def tension_band_count(analyses: list[dict[str, Any]], band: str) -> int:
    return sum(1 for item in analyses if str(item.get("tension_band") or "") == band)


def tension_type_count(analyses: list[dict[str, Any]], tension_type: str) -> int:
    return sum(1 for item in analyses if str(item.get("tension_type") or "") == tension_type)


def conflict_count(analyses: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in analyses
        if str(item.get("tension_type") or "") in {"hard_conflict", "contradiction"}
    )


def hard_conflict_count(analyses: list[dict[str, Any]]) -> int:
    return sum(1 for item in analyses if str(item.get("tension_type") or "") == "hard_conflict")


def reason_values(items: list[dict[str, Any]], key: str) -> list[str]:
    reasons: list[str] = []
    for item in items:
        raw = item.get(key)
        values = raw if isinstance(raw, list) else [raw] if raw else []
        for value in values:
            text = str(value or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def similarity_boost_reason_count(analyses: list[dict[str, Any]]) -> int:
    return sum(
        1
        for reason in reason_values(analyses, "similarity_reasons")
        if "boost" in reason or reason.startswith("name:canonical")
    )


def multilingual_alias_match_count(
    candidate_selections: list[dict[str, Any]],
    similarity_analyses: list[dict[str, Any]],
) -> int:
    count = 0
    for reason in reason_values(candidate_selections, "reasons"):
        if reason.startswith("canonical_name_match"):
            count += 1
    for reason in reason_values(similarity_analyses, "similarity_reasons"):
        if reason.startswith("name:canonical_exact"):
            count += 1
    return count


def candidate_duplicate_removed_count(candidate_selections: list[dict[str, Any]]) -> int:
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


def candidate_group_count(candidate_selections: list[dict[str, Any]]) -> int:
    keys = {
        str(item.get("candidate_canonical_key") or (item.get("merge_candidate_group") or {}).get("canonical_key") or "")
        for item in candidate_selections
    }
    keys.discard("")
    return len(keys)


def duplicate_memory_profile_count(candidate_selections: list[dict[str, Any]]) -> int:
    count = 0
    for item in candidate_selections:
        group = item.get("merge_candidate_group")
        if isinstance(group, dict):
            try:
                count += int(group.get("duplicate_memory_profile_count") or 0)
            except (TypeError, ValueError):
                continue
    return count


def candidate_score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("score") or item.get("candidate_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def dedupe_candidate_selection_dicts(candidate_selections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
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
        if candidate_score(item) > candidate_score(current):
            by_key[key] = item
    return [*passthrough, *by_key.values()], removed


def dedupe_similarity_analysis_dicts(similarity_analyses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
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
        if similarity_score(item) > similarity_score(current):
            by_key[key] = item
    return [*passthrough, *by_key.values()], removed


def canonical_entity_merge_suggestion_count(similarity_analyses: list[dict[str, Any]]) -> int:
    count = 0
    for item in similarity_analyses:
        band = str(item.get("similarity_band") or "")
        if band not in {"medium", "high"}:
            continue
        reasons = [str(reason or "") for reason in item.get("similarity_reasons") or []]
        if any(reason.startswith("name:canonical") for reason in reasons):
            count += 1
    return count


def unknown_entity_type_examples(local_entities: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
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


def bad_subject_claim_examples(quality_summary: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
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


__all__ = [
    "bad_subject_claim_examples",
    "candidate_duplicate_removed_count",
    "candidate_evidence",
    "candidate_group_count",
    "candidate_has_evidence",
    "candidate_score",
    "candidate_selection_ready",
    "candidates_without_evidence_count",
    "canonical_entity_merge_suggestion_count",
    "coerce_str_list",
    "conflict_count",
    "dedupe_candidate_selection_dicts",
    "dedupe_similarity_analysis_dicts",
    "duplicate_memory_profile_count",
    "hard_conflict_count",
    "is_uuid_string",
    "multilingual_alias_match_count",
    "quality_summary_placeholder",
    "reason_values",
    "similarity_band_count",
    "similarity_boost_reason_count",
    "similarity_ready",
    "similarity_score",
    "similarity_score_distribution",
    "similarity_without_evidence_count",
    "tension_band_count",
    "tension_type_count",
    "tension_without_evidence_count",
    "top_candidate_score",
    "unknown_entity_type_examples",
]
