# backend/apps/knowledge/service/knowledge_trace_view.py
# Feladat: Knowledge trace nézeti és log-level szűrési helper függvényeket tartalmaz. Top entity/candidate/problem listákat, merge eventeket, decision annotációt és SUMMARY/INSPECT/FULL_TRACE nézetet épít. Program-specifikus trace prezentációs utility réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any


def normalize_trace_log_level(log_level: str | None, *, debug: bool = False) -> str:
    if debug:
        return "FULL_TRACE"
    value = str(log_level or "FULL_TRACE").strip().upper()
    aliases = {"DEBUG": "FULL_TRACE", "FULL": "FULL_TRACE", "TRACE": "FULL_TRACE"}
    value = aliases.get(value, value)
    return value if value in {"SUMMARY", "INSPECT", "FULL_TRACE"} else "SUMMARY"


def score_value(item: dict[str, Any], *keys: str) -> float:
    for key in keys:
        try:
            return float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
    return 0.0


def top_entities(local_entities: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(
        local_entities,
        key=lambda item: (
            len(item.get("claim_ids") or []),
            score_value(item, "coherence_score"),
            score_value(item, "confidence"),
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


def top_candidates(candidate_selections: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(candidate_selections, key=lambda item: score_value(item, "score", "candidate_score"), reverse=True)
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


def top_problems(summary: dict[str, Any]) -> list[dict[str, Any]]:
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


def merge_events(similarity_analyses: list[dict[str, Any]], decision_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def decision_entity_fields(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_type": decision.get("decision_type") or decision.get("decision"),
        "selected_candidate_id": decision.get("selected_candidate_id") or decision.get("candidate_entity_id"),
        "selected_candidate_score": decision.get("selected_candidate_score"),
        "decision_reason": decision.get("decision_reason"),
    }


def attach_decisions_to_entity_rows(rows: list[dict[str, Any]], decision_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        annotated.append({**row, **decision_entity_fields(decision)})
    return annotated


def global_profiles_from_dicts(decision_analyses: list[dict[str, Any]], search_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def short_local_entity(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "claim_ids": list(item.get("claim_ids") or [])[:2],
        "sentence_ids": list(item.get("sentence_ids") or [])[:2],
        "evidence_refs": list(item.get("evidence_refs") or [])[:2],
    }


def sentences_without_claims(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**row, "claims": []} for row in sentences]


def apply_trace_log_level(trace: dict[str, Any], log_level: str) -> dict[str, Any]:
    level = normalize_trace_log_level(log_level)
    out = dict(trace)
    out["log_level"] = level
    out["top_entities"] = top_entities(list(trace.get("local_entities") or []))
    out["top_candidates"] = top_candidates(list(trace.get("candidate_selections") or []))
    out["top_problems"] = top_problems(dict(trace.get("summary") or {}))
    out["merge_events"] = merge_events(list(trace.get("similarity_analyses") or []), list(trace.get("decision_analyses") or []))
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
    out["sentences"] = sentences_without_claims(list(trace.get("sentences") or []))
    out["local_entities"] = [short_local_entity(item) for item in list(trace.get("local_entities") or [])]
    out["local_entity_clusters"] = []
    out["candidate_selections"] = list(trace.get("candidate_selections") or [])
    out["inspect"] = {
        "bad_subject_claim_examples": quality.get("bad_subject_claim_examples") or [],
        "rejected_claim_examples": quality.get("rejected_claim_examples") or quality.get("rejected_claims") or [],
        "noise_examples": quality.get("skipped_sentences") or [],
        "candidate_shortlist": list(trace.get("candidate_selections") or []),
    }
    return out


__all__ = [
    "apply_trace_log_level",
    "attach_decisions_to_entity_rows",
    "decision_entity_fields",
    "global_profiles_from_dicts",
    "merge_events",
    "normalize_trace_log_level",
    "score_value",
    "sentences_without_claims",
    "short_local_entity",
    "top_candidates",
    "top_entities",
    "top_problems",
]
