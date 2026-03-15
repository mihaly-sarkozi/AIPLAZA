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
    """Két időintervallum átfedésének eldöntése."""
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
    """Időátfedés score [0..1] tartományban."""
    return 1.0 if intervals_overlap(query_from, query_to, item_from, item_to) else 0.0


def get_rerank_weights(override: dict | None = None) -> dict[str, float]:
    weights = {
        "semantic_match": float(getattr(settings, "rerank_semantic_match_weight", 0.22)),
        "entity_match": float(getattr(settings, "rerank_entity_match_weight", 0.20)),
        "lexical_match": float(getattr(settings, "rerank_lexical_match_weight", 0.08)),
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
    if relation_weight > 0.0:
        depth_factor = 1.0 if relation_depth <= 1 else 0.85
        graph_component = min(1.0, graph_component + (relation_weight * depth_factor))
    score = (
        weights["semantic_match"] * float(item.get("semantic_match", 0.0))
        + weights["entity_match"] * float(item.get("entity_match", 0.0))
        + weights["lexical_match"] * float(item.get("lexical_match", 0.0))
        + weights["time_match"] * float(item.get("time_match", 0.0))
        + weights["place_match"] * float(item.get("place_match", 0.0))
        + weights["graph_proximity"] * graph_component
        + weights["relation_confidence"] * relation_confidence
        + weights["strength"] * current_strength
        + weights["confidence"] * float(item.get("confidence", 0.0))
        + weights["recency"] * float(item.get("recency", 0.0))
    )
    return score * (status_multiplier * weights["status_weight"])


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
        row["final_score"] = compute_final_score(row)
        scored.append(row)
    return sorted(scored, key=lambda x: x.get("final_score", 0.0), reverse=True)
