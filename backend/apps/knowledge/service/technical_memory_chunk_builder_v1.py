"""TechnicalEntity -> TechnicalMemoryChunk builder (v1).

Korlátok: nincs globális profil, nincs vector index, nincs retrieval chunk, nincs LLM.
Csak lokális, újraépíthető munkamemória készül a TechnicalEntity struktúrából.
"""
from __future__ import annotations

from typing import Any

from apps.knowledge.domain.technical_entity import TechnicalEntity
from apps.knowledge.domain.technical_memory_chunk import (
    TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION,
    TechnicalMemoryChunk,
)


_CLAIM_BUCKETS = (
    "identity_claims",
    "descriptor_claims",
    "state_claims",
    "relation_claims",
    "event_claims",
    "rule_claims",
    "other_claims",
)

_SUMMARY_GROUP_PRIORITY = ("relation", "rule", "state", "event", "descriptor", "other")
_SUMMARY_LABEL_BY_GROUP = {
    "relation": "kapcsolatai",
    "rule": "szabályai",
    "state": "állapotai",
    "event": "eseményei",
    "descriptor": "jellemzői",
    "other": "állításai",
}
_SUMMARY_TIME_MODE_PRIORITY = {
    "unknown": 0,
    "zero_time": 1,
    "current": 2,
    "open": 3,
    "bounded": 4,
    "event": 5,
}

_FACT_FIELDS = (
    "claim_id",
    "sentence_id",
    "claim_group",
    "claim_type",
    "predicate",
    "object_text",
    "confidence",
    "time_mode",
    "time_value",
    "space_mode",
    "space_value",
)


def _fact_from_claim_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(ref.get("claim_id") or ""),
        "sentence_id": str(ref.get("sentence_id") or ""),
        "claim_group": str(ref.get("claim_group") or ""),
        "claim_type": str(ref.get("claim_type") or ""),
        "predicate": str(ref.get("predicate") or ""),
        "object_text": ref.get("object_text"),
        "confidence": float(ref.get("confidence") or 0.0),
        "time_mode": str(ref.get("time_mode") or "unknown"),
        "time_value": ref.get("time_value"),
        "space_mode": str(ref.get("space_mode") or "unknown"),
        "space_value": ref.get("space_value"),
    }


def _facts_from_entity(entity: TechnicalEntity) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for bucket_name in _CLAIM_BUCKETS:
        for ref in getattr(entity, bucket_name, []) or []:
            if not isinstance(ref, dict):
                continue
            fact = _fact_from_claim_ref(ref)
            key = (
                fact["claim_id"],
                fact["sentence_id"],
                fact["claim_group"],
                fact["predicate"],
            )
            if key in seen:
                continue
            seen.add(key)
            facts.append(fact)
    return sorted(facts, key=lambda item: (str(item.get("sentence_id") or ""), str(item.get("claim_id") or "")))


def _display_fact(fact: dict[str, Any]) -> str:
    predicate = str(fact.get("predicate") or "").strip()
    obj = fact.get("object_text")
    obj_text = str(obj).strip() if obj is not None else ""
    if predicate and obj_text:
        return f"{predicate} → {obj_text}"
    if predicate:
        return predicate
    if obj_text:
        return obj_text
    return ""


def _summary_text(entity: TechnicalEntity, facts: list[dict[str, Any]]) -> str:
    name = entity.canonical_name or entity.normalized_key or "Unknown entity"
    if not facts:
        return f"{name}: nincs aktív claim."

    selected_group = next(
        (
            group
            for group in _SUMMARY_GROUP_PRIORITY
            if any(str(fact.get("claim_group") or "") == group for fact in facts)
        ),
        "other",
    )
    selected_facts = sorted(
        [fact for fact in facts if str(fact.get("claim_group") or "") == selected_group],
        key=lambda fact: _SUMMARY_TIME_MODE_PRIORITY.get(str(fact.get("time_mode") or "unknown"), 99),
    )
    parts = [part for fact in selected_facts for part in [_display_fact(fact)] if part]
    if not parts:
        return f"{name}: nincs aktív claim."
    label = _SUMMARY_LABEL_BY_GROUP.get(selected_group, _SUMMARY_LABEL_BY_GROUP["other"])
    return f"{name} {label}: {'; '.join(parts)}."


def _time_profile(entity: TechnicalEntity) -> dict[str, Any]:
    signature = dict(entity.time_signature or {})
    return {
        "dominant_time_mode": signature.get("dominant_time_mode") or "unknown",
        "has_current_claims": bool(signature.get("has_current_claims")),
        "has_historical_claims": bool(signature.get("has_historical_claims")),
        "time_values": list(signature.get("time_values") or []),
    }


def _space_profile(entity: TechnicalEntity) -> dict[str, Any]:
    signature = dict(entity.space_signature or {})
    return {
        "dominant_space_mode": signature.get("dominant_space_mode") or "unknown",
        "has_bounded_space": bool(signature.get("has_bounded_space")),
        "space_values": list(signature.get("space_values") or []),
    }


def _relation_profile(entity: TechnicalEntity) -> dict[str, Any]:
    signature = dict(entity.relation_signature or {})
    claim_ids = list(signature.get("claim_ids") or [])
    return {
        "relation_predicates": list(signature.get("relation_predicates") or []),
        "relation_objects": list(signature.get("relation_objects") or []),
        "relation_count": len(claim_ids),
    }


class TechnicalMemoryChunkBuilderV1:
    version: str = TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION

    def build(self, technical_entity: TechnicalEntity) -> TechnicalMemoryChunk:
        return self.build_from_technical_entity(technical_entity)

    def build_from_technical_entity(self, technical_entity: TechnicalEntity) -> TechnicalMemoryChunk:
        facts = _facts_from_entity(technical_entity)
        return TechnicalMemoryChunk(
            run_id=technical_entity.run_id,
            source_id=technical_entity.source_id,
            technical_entity_id=technical_entity.technical_entity_id,
            local_entity_id=technical_entity.local_entity_id,
            entity_name=technical_entity.canonical_name,
            entity_type=technical_entity.entity_type,
            normalized_key=technical_entity.normalized_key,
            summary_text=_summary_text(technical_entity, facts),
            facts=facts,
            time_profile=_time_profile(technical_entity),
            space_profile=_space_profile(technical_entity),
            relation_profile=_relation_profile(technical_entity),
            evidence_refs=[dict(item) for item in technical_entity.evidence_refs],
            coherence_state=technical_entity.coherence_state,
            coherence_score=float(technical_entity.coherence_score or 0.0),
            confidence=float(technical_entity.confidence or 0.0),
            builder_version=self.version,
        )

    def build_many(self, technical_entities: list[TechnicalEntity]) -> list[TechnicalMemoryChunk]:
        return [self.build_from_technical_entity(item) for item in technical_entities]


__all__ = ["TechnicalMemoryChunkBuilderV1"]
