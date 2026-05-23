from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import TYPE_CHECKING

from apps.knowledge.service.language_rules import LANGUAGE_RULES, fold_text, get_language_rules, normalize_language

if TYPE_CHECKING:
    from apps.knowledge.domain.claim import Claim


@dataclass(frozen=True)
class ClaimTypeConfig:
    claim_type: str
    claim_group: str
    identity_weight: float
    similarity_weight: float
    tension_weight: float
    conflict_behavior: str
    cardinality: str
    time_sensitive: bool


CLAIM_TYPE_CONFIGS: dict[str, ClaimTypeConfig] = {
    "identifier": ClaimTypeConfig(
        claim_type="identifier",
        claim_group="identity",
        identity_weight=1.0,
        similarity_weight=1.5,
        tension_weight=1.5,
        conflict_behavior="single_value",
        cardinality="single",
        time_sensitive=False,
    ),
    "stable_descriptor": ClaimTypeConfig(
        claim_type="stable_descriptor",
        claim_group="descriptor",
        identity_weight=0.4,
        similarity_weight=1.2,
        tension_weight=0.8,
        conflict_behavior="additive",
        cardinality="multi",
        time_sensitive=False,
    ),
    "state": ClaimTypeConfig(
        claim_type="state",
        claim_group="state",
        identity_weight=0.2,
        similarity_weight=0.9,
        tension_weight=1.2,
        conflict_behavior="temporal",
        cardinality="temporal_multi",
        time_sensitive=True,
    ),
    "relation": ClaimTypeConfig(
        claim_type="relation",
        claim_group="relation",
        identity_weight=0.6,
        similarity_weight=1.3,
        tension_weight=1.1,
        conflict_behavior="additive",
        cardinality="multi",
        time_sensitive=True,
    ),
    "event": ClaimTypeConfig(
        claim_type="event",
        claim_group="event",
        identity_weight=0.2,
        similarity_weight=0.8,
        tension_weight=0.6,
        conflict_behavior="temporal",
        cardinality="multi",
        time_sensitive=True,
    ),
    "rule_procedure": ClaimTypeConfig(
        claim_type="rule_procedure",
        claim_group="rule",
        identity_weight=0.3,
        similarity_weight=1.0,
        tension_weight=1.0,
        conflict_behavior="exclusive",
        cardinality="multi",
        time_sensitive=False,
    ),
    "opinion": ClaimTypeConfig(
        claim_type="opinion",
        claim_group="evaluation",
        identity_weight=0.0,
        similarity_weight=0.4,
        tension_weight=0.3,
        conflict_behavior="weak",
        cardinality="multi",
        time_sensitive=True,
    ),
    "context_header": ClaimTypeConfig(
        claim_type="context_header",
        claim_group="other",
        identity_weight=0.0,
        similarity_weight=0.1,
        tension_weight=0.0,
        conflict_behavior="weak",
        cardinality="multi",
        time_sensitive=False,
    ),
    "other": ClaimTypeConfig(
        claim_type="other",
        claim_group="other",
        identity_weight=0.0,
        similarity_weight=0.5,
        tension_weight=0.5,
        conflict_behavior="weak",
        cardinality="multi",
        time_sensitive=False,
    ),
}


def _normalize(value: str | None) -> str:
    return fold_text((value or "").strip())


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(r"\b" + re.escape(_normalize(keyword)) + r"\b", _normalize(text), flags=re.IGNORECASE) is not None


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def apply_claim_type_config(claim: Claim) -> Claim:
    config = CLAIM_TYPE_CONFIGS.get(claim.claim_type, CLAIM_TYPE_CONFIGS["other"])
    return replace(
        claim,
        claim_group=config.claim_group,
        identity_weight=config.identity_weight,
        similarity_weight=config.similarity_weight,
        tension_weight=config.tension_weight,
        conflict_behavior=config.conflict_behavior,
        cardinality=config.cardinality,
        metadata={
            **dict(claim.metadata or {}),
            "time_sensitive": config.time_sensitive,
            "claim_type_config_applied": config.claim_type,
        },
    )


def guess_claim_type(predicate: str, object_text: str | None, claim_text: str, language: str | None = None) -> str:
    haystack = _normalize(" ".join(part for part in [predicate, object_text or "", claim_text] if part))
    normalized_language = normalize_language(language)
    rule_sets = [get_language_rules(normalized_language)] if normalized_language else list(LANGUAGE_RULES.values())
    for rules in rule_sets:
        if _matches_any(haystack, rules.claim_type_keywords.get("identifier", ())):
            return "identifier"
        if _matches_any(haystack, rules.claim_type_keywords.get("rule_procedure", ())):
            return "rule_procedure"
        if _matches_any(haystack, rules.claim_type_keywords.get("stable_descriptor", ())):
            return "stable_descriptor"
        if _matches_any(haystack, rules.claim_type_keywords.get("state", ())):
            return "state"
        if _matches_any(haystack, rules.claim_type_keywords.get("relation", ())):
            return "relation"
        if _matches_any(haystack, rules.claim_type_keywords.get("event", ())):
            return "event"
        if _matches_any(haystack, rules.claim_type_keywords.get("opinion", ())):
            return "opinion"
    return "other"


def debug_claim_type(claim: Claim) -> None:
    print(
        f"[CLAIM TYPE] type={claim.claim_type} group={claim.claim_group} "
        f"id_w={claim.identity_weight} sim_w={claim.similarity_weight} "
        f"tension_w={claim.tension_weight} behavior={claim.conflict_behavior}"
    )


__all__ = [
    "CLAIM_TYPE_CONFIGS",
    "ClaimTypeConfig",
    "apply_claim_type_config",
    "debug_claim_type",
    "guess_claim_type",
]
