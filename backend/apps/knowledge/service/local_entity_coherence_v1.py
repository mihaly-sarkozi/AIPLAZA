"""Lokális entitás-klaszter kohéziós pontszám (v1, DB nélkül).

**Tiltások** ugyanazok, mint a ``local_resolver_v1`` modulban (globális profil, Qdrant, cross-doc/lang, LLM, fuzzy, tension).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from apps.knowledge.domain.claim import ClaimStatus
from apps.knowledge.domain.local_entity_cluster import LocalEntityType

__all__ = ["coherence_factors_v1", "coherence_score_v1"]


def _norm_time_label_for_coherence(claim: Any) -> str:
    tl = getattr(claim, "time_label", None)
    if tl is None:
        return ""
    return str(tl).strip().lower()


def _claim_group_time_state_conflict(claims: list[Any]) -> bool:
    """Ugyanazon claim_group + idő kulcs mellett ellentétes claim_status (v1, egyszerű)."""
    by_key: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for c in claims:
        cg = str(getattr(c, "claim_group", "") or "default")
        tm = str(getattr(c, "time_mode", "") or "unknown")
        tl = _norm_time_label_for_coherence(c)
        by_key[(cg, tm, tl)].append(c)
    for clist in by_key.values():
        if len(clist) < 2:
            continue
        statuses = {str(getattr(c, "claim_status", "") or ClaimStatus.ACTIVE.value) for c in clist}
        if ClaimStatus.ACTIVE.value in statuses and ClaimStatus.BANNED.value in statuses:
            return True
        if ClaimStatus.ACTIVE.value in statuses and ClaimStatus.WEAKENED.value in statuses:
            return True
    return False


def coherence_score_v1(
    claims: list[Any],
    *,
    entity_type: str,
    unique_claim_subject_surfaces: set[str],
    avg_confidence: float,
) -> float:
    """Alap 1.0; egyszerű büntetések v1-ben (nincs tension engine). Eredmény [0, 1]."""
    score = 1.0

    ctypes = {str(getattr(c, "claim_type", "") or "") for c in claims}
    ctypes.discard("")
    if len(ctypes) > 1:
        score -= 0.1

    if _claim_group_time_state_conflict(claims):
        score -= 0.3

    if len(unique_claim_subject_surfaces) > 1:
        score -= 0.1

    if entity_type == LocalEntityType.UNKNOWN.value:
        score -= 0.1

    if avg_confidence < 0.7:
        score -= 0.1

    return max(0.0, min(1.0, score))


def coherence_factors_v1(
    claims: list[Any],
    *,
    entity_type: str,
    unique_claim_subject_surfaces: set[str],
    avg_confidence: float,
) -> list[str]:
    """Emberi olvasásra szánt faktorok: miért tartoznak egy klaszterbe / mi bünteti a kohéziót."""
    factors: list[str] = ["same_normalized_key"]
    if entity_type != LocalEntityType.UNKNOWN.value:
        factors.append("matching_entity_type")
    else:
        factors.append("entity_type=unknown")
    factors.append(f"avg_claim_confidence={avg_confidence:.2f}")

    ctypes = {str(getattr(c, "claim_type", "") or "") for c in claims}
    ctypes.discard("")
    if len(ctypes) > 1:
        factors.append("coherence_penalty:multiple_claim_types")
    if _claim_group_time_state_conflict(claims):
        factors.append("coherence_penalty:claim_group_time_state_conflict")
    if len(unique_claim_subject_surfaces) > 1:
        factors.append("coherence_penalty:multiple_subject_surfaces")
    if entity_type == LocalEntityType.UNKNOWN.value:
        factors.append("coherence_penalty:unknown_entity_type")
    if avg_confidence < 0.7:
        factors.append("coherence_penalty:low_avg_confidence")
    return factors
