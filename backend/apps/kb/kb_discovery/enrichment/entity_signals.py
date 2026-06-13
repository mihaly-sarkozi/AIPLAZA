from __future__ import annotations

from collections import Counter

from apps.kb.kb_discovery.orm.EntityMention import EntityMention

_ENTITY_TOPIC_BOOSTS: dict[str, tuple[str, ...]] = {
    "company": ("operations", "legal"),
    "system": ("integration", "sales"),
    "product": ("sales", "document_management"),
    "contract_id": ("legal", "document_management"),
    "invoice_id": ("billing",),
    "person": ("hr", "support"),
}


def entity_signals(mentions: list[EntityMention]) -> dict[str, object]:
    types = Counter(str(item.entity_type or "other") for item in mentions)
    return {
        "entity_count": len(mentions),
        "entity_types": sorted(types.keys()),
        "entity_type_counts": dict(types),
    }


def topic_boosts_from_entities(mentions: list[EntityMention]) -> dict[str, float]:
    boosts: dict[str, float] = {}
    for mention in mentions:
        topics = _ENTITY_TOPIC_BOOSTS.get(str(mention.entity_type or "").lower(), ())
        for topic_key in topics:
            boosts[topic_key] = boosts.get(topic_key, 0.0) + 0.25
    return boosts


def keyword_boosts_from_entities(mentions: list[EntityMention]) -> list[tuple[str, float, dict[str, object]]]:
    boosted: list[tuple[str, float, dict[str, object]]] = []
    for mention in mentions:
        raw = str(mention.raw_text or "").strip()
        if len(raw) < 2:
            continue
        boosted.append(
            (
                raw,
                0.85,
                {
                    "source": "entity_derived",
                    "entity_type": mention.entity_type,
                    "confidence": mention.confidence,
                },
            )
        )
    return boosted


__all__ = ["entity_signals", "keyword_boosts_from_entities", "topic_boosts_from_entities"]
