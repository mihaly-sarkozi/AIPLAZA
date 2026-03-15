from __future__ import annotations

from datetime import UTC, datetime
from math import exp

EVENT_ALPHA_DEFAULT = {
    "EXPLICIT_TRAINING": 0.35,
    "SOURCE_CONFIRMATION": 0.25,
    "CHAT_RETRIEVAL_HIT": 0.10,
    "USER_FOLLOWUP": 0.12,
    "USER_CONFIRMATION": 0.30,
    "INDIRECT_ACTIVATION": 0.08,
}


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return datetime.now(UTC).replace(tzinfo=None)


def compute_initial_confidence(
    extraction_confidence: float,
    source_quality: float,
    evidence_count: int,
    source_diversity: int,
) -> float:
    """Confidence becslés extraction + evidencia alapján."""
    comps = compute_confidence_components(
        extraction_confidence=extraction_confidence,
        source_quality=source_quality,
        evidence_count=evidence_count,
        source_diversity=source_diversity,
        contradiction_penalty=0.0,
    )
    return float(comps["final_confidence"])


def compute_confidence_components(
    extraction_confidence: float,
    source_quality: float,
    evidence_count: int,
    source_diversity: int,
    contradiction_penalty: float = 0.0,
) -> dict[str, float]:
    """Confidence komponensek: extraction + evidence + diversity - contradiction."""
    extraction_component = max(0.0, min(1.0, float(extraction_confidence)))
    source_component = max(0.0, min(1.0, float(source_quality)))
    evidence_support_score = max(0.0, min(1.0, 0.4 + 0.08 * max(0, int(evidence_count) - 1)))
    source_diversity_score = max(0.0, min(1.0, 0.35 + 0.12 * max(0, int(source_diversity) - 1)))
    contradiction_penalty = max(0.0, min(0.5, float(contradiction_penalty)))
    final = (
        (0.42 * extraction_component)
        + (0.18 * source_component)
        + (0.22 * evidence_support_score)
        + (0.18 * source_diversity_score)
        - contradiction_penalty
    )
    return {
        "extraction_confidence": extraction_component,
        "source_quality": source_component,
        "evidence_support_score": evidence_support_score,
        "source_diversity_score": source_diversity_score,
        "contradiction_penalty": contradiction_penalty,
        "final_confidence": max(0.0, min(1.0, final)),
    }


def compute_relation_confidence(
    relation_weight: float,
    evidence_overlap_count: int = 0,
    contradiction_signals: int = 0,
) -> float:
    """Relation confidence külön becslése zajos relationök szűréséhez."""
    base = max(0.0, min(1.0, float(relation_weight)))
    ev_boost = min(0.2, 0.04 * max(0, int(evidence_overlap_count)))
    contradiction_penalty = min(0.35, 0.08 * max(0, int(contradiction_signals)))
    return max(0.0, min(1.0, base + ev_boost - contradiction_penalty))


def compute_confidence(
    extraction_confidence: float,
    source_quality: float,
    evidence_count: int,
    source_diversity: int,
) -> float:
    """Kompatibilis alias a kezdeti confidence számításhoz."""
    return compute_initial_confidence(
        extraction_confidence=extraction_confidence,
        source_quality=source_quality,
        evidence_count=evidence_count,
        source_diversity=source_diversity,
    )


def compute_initial_strength(baseline_strength: float = 0.05) -> float:
    """Kezdeti strength érték."""
    return max(0.01, min(1.0, baseline_strength))


def normalize_event_type(event_type: str | None) -> str:
    raw = str(event_type or "").strip().upper()
    compat = {
        "EXPLICIT_TRAINING": "EXPLICIT_TRAINING",
        "SOURCE_CONFIRMATION": "SOURCE_CONFIRMATION",
        "CHAT_RETRIEVAL_HIT": "CHAT_RETRIEVAL_HIT",
        "USER_FOLLOWUP": "USER_FOLLOWUP",
        "USER_CONFIRMATION": "USER_CONFIRMATION",
        "INDIRECT_ACTIVATION": "INDIRECT_ACTIVATION",
        # backward compat
        "EXPLICIT_TRAINING_OLD": "EXPLICIT_TRAINING",
        "RETRIEVAL_HIT": "CHAT_RETRIEVAL_HIT",
        "FOLLOWUP": "USER_FOLLOWUP",
        "SOURCE_CONFIRM": "SOURCE_CONFIRMATION",
    }
    return compat.get(raw, raw or "CHAT_RETRIEVAL_HIT")


def alpha_for_event(event_type: str | None) -> float:
    event = normalize_event_type(event_type)
    return float(EVENT_ALPHA_DEFAULT.get(event, EVENT_ALPHA_DEFAULT["CHAT_RETRIEVAL_HIT"]))


def decay_strength(
    current_strength: float,
    baseline_strength: float,
    decay_rate: float,
    delta_days: float,
) -> float:
    """Időalapú strength csökkenés (baseline fölött exponenciálisan)."""
    decayed = baseline_strength + (current_strength - baseline_strength) * exp(-decay_rate * max(0.0, delta_days))
    return max(baseline_strength, decayed)


def reinforce_strength(old_strength: float, alpha: float, baseline_strength: float = 0.05) -> float:
    """Reinforcement esemény utáni strength frissítés."""
    value = old_strength + alpha * (1.0 - old_strength)
    return max(baseline_strength, min(1.0, value))


def compute_delta_days(last_at: datetime | None, now: datetime | None = None) -> float:
    """Napkülönbség két időpont között."""
    if last_at is None:
        return 0.0
    current = now or _utcnow_naive()
    return max(0.0, (current - last_at).total_seconds() / 86400.0)


def compute_current_strength(
    strength: float,
    baseline_strength: float,
    decay_rate: float,
    last_reinforced_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """Aktuális (decayed) strength lekérdezés időpillanatra."""
    return decay_strength(
        current_strength=float(strength),
        baseline_strength=float(baseline_strength),
        decay_rate=float(decay_rate),
        delta_days=compute_delta_days(last_reinforced_at, now=now),
    )


def determine_assertion_status(
    confidence: float,
    evidence_count: int,
    relations: list[dict] | None = None,
    conflict_candidate: bool = False,
    superseded_hint: bool = False,
    refined_hint: bool = False,
    generalized_hint: bool = False,
    partial_superseded_hint: bool = False,
) -> str:
    """Assertion státusz becslés (P2 lifecycle)."""
    rel_types = {str(x.get("relation_type") or "").upper() for x in (relations or [])}
    if "CONTRADICTS" in rel_types:
        conflict_candidate = True
    if "REFINES" in rel_types:
        refined_hint = True
    if "GENERALIZES" in rel_types:
        generalized_hint = True
    if "TEMPORALLY_SPLITS" in rel_types:
        partial_superseded_hint = True
    if conflict_candidate:
        return "conflicted"
    if refined_hint:
        return "refined"
    if generalized_hint:
        return "generalized"
    if partial_superseded_hint:
        return "partially_superseded"
    if superseded_hint:
        return "superseded"
    if float(confidence) < 0.45 and int(evidence_count) <= 1:
        return "uncertain"
    return "active"


def recompute_assertion_score_fields(
    extraction_confidence: float,
    source_quality: float,
    evidence_count: int,
    source_diversity: int,
    old_strength: float,
    baseline_strength: float,
    decay_rate: float,
    last_reinforced_at: datetime | None,
    now: datetime | None = None,
    reinforce_alpha: float | None = None,
) -> dict:
    """Assertion confidence/strength mezők újraszámolása egyben."""
    delta_days = compute_delta_days(last_reinforced_at, now=now)
    decayed_strength = decay_strength(
        current_strength=old_strength,
        baseline_strength=baseline_strength,
        decay_rate=decay_rate,
        delta_days=delta_days,
    )
    if reinforce_alpha is not None:
        decayed_strength = reinforce_strength(
            old_strength=decayed_strength,
            alpha=reinforce_alpha,
            baseline_strength=baseline_strength,
        )
    return {
        "confidence": compute_initial_confidence(
            extraction_confidence=extraction_confidence,
            source_quality=source_quality,
            evidence_count=evidence_count,
            source_diversity=source_diversity,
        ),
        "strength": decayed_strength,
    }
