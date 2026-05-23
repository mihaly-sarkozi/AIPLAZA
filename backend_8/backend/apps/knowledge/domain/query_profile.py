from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


QUERY_RESOLVER_VERSION = "query_resolver_v0"


@dataclass(frozen=True)
class QueryProfile:
    entity_type: str | None = None
    entity: str | None = None
    intent: str = "unknown"
    relation_predicate: str | None = None
    relation_object: str | None = None
    rule_action: str | None = None
    expected_answer_type: str | None = None
    state: str | None = None
    time_filter: str | None = None
    space_filter: str | None = None
    keywords: list[str] = field(default_factory=list)
    detected_entities: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    builder_version: str = QUERY_RESOLVER_VERSION


def query_profile_to_json_dict(profile: QueryProfile) -> dict[str, Any]:
    return {
        "entity_type": profile.entity_type,
        "entity": profile.entity,
        "intent": profile.intent,
        "relation_predicate": profile.relation_predicate,
        "relation_object": profile.relation_object,
        "rule_action": profile.rule_action,
        "expected_answer_type": profile.expected_answer_type,
        "state": profile.state,
        "time_filter": profile.time_filter,
        "space_filter": profile.space_filter,
        "keywords": list(profile.keywords),
        "detected_entities": [dict(item) for item in profile.detected_entities],
        "confidence": round(float(profile.confidence or 0.0), 4),
        "reasons": list(profile.reasons),
        "builder_version": profile.builder_version,
    }


__all__ = ["QUERY_RESOLVER_VERSION", "QueryProfile", "query_profile_to_json_dict"]
