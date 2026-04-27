"""LocalEntityCluster -> TechnicalEntity builder (v1).

Korlátok: nincs globális profil, nincs similarity/tension engine, nincs Qdrant, nincs LLM.
Csak a lokális klaszterekből és opcionálisan átadott claim objektumokból készít összehasonlítható struktúrát.
"""
from __future__ import annotations

from typing import Any

from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.technical_entity import TECHNICAL_ENTITY_BUILDER_VERSION, TechnicalEntity


_CLAIM_BUCKET_BY_GROUP = {
    "identity": "identity_claims",
    "descriptor": "descriptor_claims",
    "state": "state_claims",
    "relation": "relation_claims",
    "event": "event_claims",
    "rule": "rule_claims",
}


def _claim_id(value: Any) -> str:
    return str(getattr(value, "claim_id", "") or getattr(value, "id", "") or "")


def _claim_type(value: Any) -> str:
    return str(getattr(value, "claim_type", "") or "")


def _claim_group(value: Any) -> str:
    return str(getattr(value, "claim_group", "") or "")


def _claim_ref(value: Any) -> dict[str, Any]:
    time_value = getattr(value, "time_label", None)
    if time_value is None:
        time_value = getattr(value, "time_value", None)
    space_value = getattr(value, "space_label", None)
    if space_value is None:
        space_value = getattr(value, "space_value", None)
    return {
        "claim_id": _claim_id(value),
        "sentence_id": str(getattr(value, "sentence_id", "") or ""),
        "predicate": str(getattr(value, "predicate_text", "") or getattr(value, "predicate", "") or ""),
        "object_text": getattr(value, "object_text", None),
        "claim_type": _claim_type(value),
        "claim_group": _claim_group(value),
        "confidence": float(getattr(value, "confidence", 0.0) or 0.0),
        "time_mode": str(getattr(value, "time_mode", "") or "unknown"),
        "time_value": time_value,
        "space_mode": str(getattr(value, "space_mode", "") or "unknown"),
        "space_value": space_value,
    }


def _evidence_ref_as_claim_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(ref.get("claim_id") or ""),
        "sentence_id": str(ref.get("sentence_id") or ""),
        "predicate": str(ref.get("predicate") or ""),
        "object_text": ref.get("object_text"),
        "claim_type": str(ref.get("claim_type") or ""),
        "claim_group": str(ref.get("claim_group") or ""),
        "confidence": float(ref.get("confidence") or 0.0),
        "time_mode": str(ref.get("time_mode") or "unknown"),
        "time_value": ref.get("time_value"),
        "space_mode": str(ref.get("space_mode") or "unknown"),
        "space_value": ref.get("space_value"),
    }


def _bucket_name(claim_ref: dict[str, Any]) -> str:
    return _CLAIM_BUCKET_BY_GROUP.get(str(claim_ref.get("claim_group") or ""), "other_claims")


def _append_unique_text(values: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _signature_from_claims(claim_refs: list[dict[str, Any]], *, prefix: str) -> dict[str, Any]:
    modes: list[str] = []
    values: list[str] = []
    claim_ids: list[str] = []
    for ref in claim_refs:
        _append_unique_text(modes, ref.get(f"{prefix}_mode"))
        _append_unique_text(values, ref.get(f"{prefix}_value"))
        _append_unique_text(claim_ids, ref.get("claim_id"))
    return {
        "modes": sorted(modes),
        "values": sorted(values),
        "claim_ids": sorted(claim_ids),
    }


def _time_signature(claim_refs: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[str] = []
    modes: list[str] = []
    for ref in claim_refs:
        mode = str(ref.get("time_mode") or "unknown")
        modes.append(mode)
        _append_unique_text(values, ref.get("time_value"))

    has_current = any(mode == "current" for mode in modes)
    has_historical = any(mode in {"bounded", "event"} for mode in modes)
    if has_current:
        dominant = "current"
    elif has_historical:
        dominant = "historical"
    elif any(mode == "zero_time" for mode in modes):
        dominant = "timeless"
    else:
        dominant = "unknown"
    return {
        "has_current_claims": has_current,
        "has_historical_claims": has_historical,
        "time_values": sorted(values),
        "dominant_time_mode": dominant,
    }


def _space_signature(claim_refs: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[str] = []
    modes: list[str] = []
    for ref in claim_refs:
        mode = str(ref.get("space_mode") or "unknown")
        modes.append(mode)
        _append_unique_text(values, ref.get("space_value"))

    has_bounded = any(mode == "bounded" for mode in modes)
    if has_bounded:
        dominant = "bounded"
    elif any(mode in {"irrelevant", "location_independent"} for mode in modes):
        dominant = "irrelevant"
    else:
        dominant = "unknown"
    return {
        "has_bounded_space": has_bounded,
        "space_values": sorted(values),
        "dominant_space_mode": dominant,
    }


def _relation_signature(claim_refs: list[dict[str, Any]]) -> dict[str, Any]:
    predicates: list[str] = []
    objects: list[str] = []
    claim_ids: list[str] = []
    for ref in claim_refs:
        _append_unique_text(predicates, ref.get("predicate"))
        _append_unique_text(objects, ref.get("object_text"))
        _append_unique_text(claim_ids, ref.get("claim_id"))
    return {
        "relation_predicates": sorted(predicates),
        "relation_objects": sorted(objects),
        "claim_ids": sorted(claim_ids),
    }


def _coherence_state(score: float) -> str:
    if score >= 0.85:
        return "stable"
    if score >= 0.60:
        return "uncertain"
    return "problematic"


class TechnicalEntityBuilderV1:
    version: str = TECHNICAL_ENTITY_BUILDER_VERSION

    def build_from_local_entity(self, local_entity) -> TechnicalEntity:
        """Public v1 API: egy LocalEntityCluster -> TechnicalEntity."""
        return self.build_one(local_entity)

    def build_many(self, local_entities: list) -> list[TechnicalEntity]:
        """Public v1 API: több LocalEntityCluster -> TechnicalEntity lista."""
        return [self.build_from_local_entity(item) for item in local_entities]

    def build(
        self,
        clusters: list[LocalEntityCluster],
        *,
        claims: list[Any] | None = None,
    ) -> list[TechnicalEntity]:
        claim_by_id = {str(_claim_id(item)): item for item in (claims or []) if _claim_id(item)}
        return [self.build_one(cluster, claim_by_id=claim_by_id) for cluster in clusters]

    def build_one(
        self,
        cluster: LocalEntityCluster,
        *,
        claim_by_id: dict[str, Any] | None = None,
    ) -> TechnicalEntity:
        claim_by_id = claim_by_id or {}
        claim_refs = self._claim_refs_for_cluster(cluster, claim_by_id=claim_by_id)
        buckets: dict[str, list[dict[str, Any]]] = {
            "identity_claims": [],
            "descriptor_claims": [],
            "state_claims": [],
            "relation_claims": [],
            "event_claims": [],
            "rule_claims": [],
            "other_claims": [],
        }
        for ref in claim_refs:
            buckets[_bucket_name(ref)].append(ref)

        surface_forms = sorted({str(item).strip() for item in cluster.surface_forms if str(item).strip()})
        explanation = dict(getattr(cluster, "explanation", {}) or {})
        canonical_key = str(explanation.get("canonical_key") or cluster.normalized_key or "")
        surface_bundle = {
            "canonical_name": cluster.canonical_name,
            "normalized_key": cluster.normalized_key,
            "canonical_key": canonical_key,
            "surface_forms": surface_forms,
            "aliases": list(surface_forms),
            "mention_texts": list(surface_forms),
            "surface_count": len(surface_forms),
            "mention_ids": [str(item) for item in cluster.mention_ids],
            "sentence_ids": [str(item) for item in cluster.sentence_ids],
        }

        return TechnicalEntity(
            run_id=cluster.run_id,
            source_id=cluster.source_id,
            local_entity_id=cluster.local_entity_id,
            canonical_name=cluster.canonical_name,
            entity_type=cluster.entity_type,
            normalized_key=cluster.normalized_key,
            canonical_key=canonical_key,
            surface_bundle=surface_bundle,
            identity_claims=buckets["identity_claims"],
            descriptor_claims=buckets["descriptor_claims"],
            state_claims=buckets["state_claims"],
            relation_claims=buckets["relation_claims"],
            event_claims=buckets["event_claims"],
            rule_claims=buckets["rule_claims"],
            other_claims=buckets["other_claims"],
            time_signature=_time_signature(claim_refs),
            space_signature=_space_signature(claim_refs),
            relation_signature=_relation_signature(buckets["relation_claims"]),
            evidence_refs=[dict(item) for item in cluster.evidence_refs],
            coherence_state=_coherence_state(float(cluster.coherence_score or 0.0)),
            coherence_score=float(cluster.coherence_score or 0.0),
            confidence=float(cluster.confidence or 0.0),
            builder_version=self.version,
        )

    def _claim_refs_for_cluster(
        self,
        cluster: LocalEntityCluster,
        *,
        claim_by_id: dict[str, Any],
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for claim_uuid in cluster.claim_ids:
            cid = str(claim_uuid)
            claim = claim_by_id.get(cid)
            if claim is not None:
                refs.append(_claim_ref(claim))
                continue
            evidence = next((item for item in cluster.evidence_refs if str(item.get("claim_id") or "") == cid), None)
            if isinstance(evidence, dict):
                refs.append(_evidence_ref_as_claim_ref(evidence))
        if refs:
            return sorted(refs, key=lambda item: (str(item.get("sentence_id") or ""), str(item.get("claim_id") or "")))
        return sorted(
            [_evidence_ref_as_claim_ref(item) for item in cluster.evidence_refs if isinstance(item, dict)],
            key=lambda item: (str(item.get("sentence_id") or ""), str(item.get("claim_id") or "")),
        )


__all__ = ["TechnicalEntityBuilderV1"]
