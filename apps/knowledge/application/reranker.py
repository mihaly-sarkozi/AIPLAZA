from __future__ import annotations

from datetime import datetime

from apps.knowledge.application.scoring import compute_current_strength
from config.settings import settings


def _to_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def intervals_overlap(query_from, query_to, item_from, item_to) -> bool:
    """Két valid_time intervallum átfedésének eldöntése."""
    qf = _to_datetime(query_from)
    qt = _to_datetime(query_to)
    if qf is None and qt is None:
        return False
    if qf is None:
        qf = qt
    if qt is None:
        qt = qf
    itf = _to_datetime(item_from)
    itt = _to_datetime(item_to)
    if itf is None and itt is None:
        return False
    if itf is None:
        itf = itt
    if itt is None:
        itt = itf
    if qf is None or qt is None or itf is None or itt is None:
        return False
    return not (itt < qf or qt < itf)


def compute_time_overlap_score(query_from, query_to, item_from, item_to) -> float:
    """Valid_time átfedés score [0..1] tartományban."""
    return 1.0 if intervals_overlap(query_from, query_to, item_from, item_to) else 0.0


def compute_recency_score(source_time, ingest_time, now: datetime | None = None) -> float:
    """Recency score csak source/ingest idő alapján (nem valid_time)."""
    reference = _to_datetime(source_time) or _to_datetime(ingest_time)
    if reference is None:
        return 0.0
    current = now or datetime.utcnow()
    delta_days = max(0.0, (current - reference).total_seconds() / 86400.0)
    # ~6 hónapos felezési jellegű lecsengés.
    return max(0.0, min(1.0, 1.0 / (1.0 + (delta_days / 180.0))))


def get_rerank_weights(override: dict | None = None) -> dict[str, float]:
    weights = {
        "semantic_match": float(getattr(settings, "rerank_semantic_match_weight", 0.22)),
        "entity_match": float(getattr(settings, "rerank_entity_match_weight", 0.20)),
        "predicate_match": float(getattr(settings, "rerank_predicate_match_weight", 0.08)),
        "lexical_match": float(getattr(settings, "rerank_lexical_match_weight", 0.08)),
        "fusion_match": float(getattr(settings, "rerank_fusion_match_weight", 0.06)),
        "time_match": float(getattr(settings, "rerank_time_match_weight", 0.16)),
        "place_match": float(getattr(settings, "rerank_place_match_weight", 0.08)),
        "graph_proximity": float(getattr(settings, "rerank_graph_proximity_weight", 0.10)),
        "relation_confidence": float(getattr(settings, "rerank_relation_confidence_weight", 0.06)),
        "strength": float(getattr(settings, "rerank_strength_weight", 0.10)),
        "confidence": float(getattr(settings, "rerank_confidence_weight", 0.10)),
        "recency": float(getattr(settings, "rerank_recency_weight", 0.04)),
        "status_weight": float(getattr(settings, "rerank_status_weight", 1.0)),
    }
    if override:
        for key, value in override.items():
            if key in weights:
                weights[key] = float(value)
    return weights


def compute_final_score(item: dict) -> float:
    """MVP rerank score a megadott súlyokkal."""
    weights = get_rerank_weights(item.get("weights") if isinstance(item.get("weights"), dict) else None)
    current_strength = compute_current_strength(
        strength=float(item.get("strength", 0.0)),
        baseline_strength=float(item.get("baseline_strength", 0.05)),
        decay_rate=float(item.get("decay_rate", 0.015)),
        last_reinforced_at=_to_datetime(item.get("last_reinforced_at")),
    )
    status = str(item.get("status") or "active").lower()
    status_multiplier = {
        "active": 1.0,
        "uncertain": 0.75,
        "superseded": 0.60,
        "partially_superseded": 0.72,
        "generalized": 0.78,
        "refined": 1.05,
        "conflicted": 0.50,
    }.get(status, 1.0)
    graph_component = float(item.get("graph_proximity", 0.0))
    relation_weight = float(item.get("relation_weight", 0.0))
    relation_confidence = float(item.get("relation_confidence", 0.0))
    relation_depth = int(item.get("relation_depth") or 1)
    relation_type = str(item.get("relation_type") or "").upper()
    relation_type_factor = {
        "SUPPORTS": 1.0,
        "REFINES": 0.95,
        "GENERALIZES": 0.82,
        "CONTRADICTS": 0.72,
        "TEMPORALLY_SPLITS": 0.84,
        "TEMPORALLY_OVERLAPS": 0.78,
        "SAME_SUBJECT": 0.72,
        "SAME_OBJECT": 0.68,
        "SAME_PREDICATE": 0.62,
        "SAME_PLACE": 0.60,
        "SAME_SOURCE_POINT": 0.45,
    }.get(relation_type, 0.62)
    if relation_weight > 0.0:
        depth_factor = 1.0 if relation_depth <= 1 else 0.85
        relation_graph_signal = relation_weight * (0.35 + (0.65 * relation_confidence)) * relation_type_factor
        graph_component = min(1.0, graph_component + (relation_graph_signal * depth_factor))
    place_match = float(item.get("place_match", 0.0))
    if place_match > 0.0:
        place_context_density = min(
            1.0,
            0.15 * len(item.get("place_ids") or [])
            + 0.08 * len(item.get("place_hierarchy_keys") or []),
        )
        place_match = min(1.0, place_match + place_context_density)
    recency_score = compute_recency_score(
        source_time=item.get("source_time"),
        ingest_time=item.get("ingest_time"),
    )
    score = (
        weights["semantic_match"] * float(item.get("semantic_match", 0.0))
        + weights["entity_match"] * float(item.get("entity_match", 0.0))
        + weights["predicate_match"] * float(item.get("predicate_match", 0.0))
        + weights["lexical_match"] * float(item.get("lexical_match", 0.0))
        + weights["fusion_match"] * float(item.get("fusion_match", 0.0))
        + weights["time_match"] * float(item.get("time_match", 0.0))
        + weights["place_match"] * place_match
        + weights["graph_proximity"] * graph_component
        + weights["relation_confidence"] * relation_confidence
        + weights["strength"] * current_strength
        + weights["confidence"] * float(item.get("confidence", 0.0))
        + weights["recency"] * recency_score
    )
    return score * (status_multiplier * weights["status_weight"])


def compute_local_context_score(item: dict) -> float:
    """Lokális assertion-neighborhood score seed körüli bővítéshez."""
    relation_confidence = float(item.get("relation_confidence", 0.0))
    relation_weight = float(item.get("relation_weight", 0.0))
    entity_match = float(item.get("entity_match", 0.0))
    time_match = float(item.get("time_match", 0.0))
    place_match = float(item.get("place_match", 0.0))
    graph_proximity = float(item.get("graph_proximity", 0.0))
    fusion_match = float(item.get("fusion_match", 0.0))
    predicate_match = float(item.get("predicate_match", 0.0))
    evidence_bridge = float(item.get("evidence_bridge_score", 0.0))
    support_signal = (
        (0.24 * relation_confidence)
        + (0.16 * relation_weight)
        + (0.16 * entity_match)
        + (0.14 * time_match)
        + (0.10 * place_match)
        + (0.10 * graph_proximity)
        + (0.05 * predicate_match)
        + (0.05 * evidence_bridge)
    )
    return max(
        0.0,
        min(
            1.0,
            support_signal + (0.10 * float(item.get("confidence", 0.0))) + (0.05 * fusion_match),
        ),
    )


def rerank_items(items: list[dict]) -> list[dict]:
    """Rangsorolás a composite score alapján."""
    scored = []
    for item in items:
        row = dict(item)
        row["current_strength"] = compute_current_strength(
            strength=float(row.get("strength", 0.0)),
            baseline_strength=float(row.get("baseline_strength", 0.05)),
            decay_rate=float(row.get("decay_rate", 0.015)),
            last_reinforced_at=_to_datetime(row.get("last_reinforced_at")),
        )
        row["recency_score"] = compute_recency_score(
            source_time=row.get("source_time"),
            ingest_time=row.get("ingest_time"),
        )
        row["local_context_score"] = compute_local_context_score(row)
        row["final_score"] = compute_final_score(row)
        scored.append(row)
    return sorted(scored, key=lambda x: x.get("final_score", 0.0), reverse=True)
