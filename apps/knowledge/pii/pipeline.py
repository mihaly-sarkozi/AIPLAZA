# apps/knowledge/pii/pipeline.py
"""
Thin compatibility layer: exposes legacy API by delegating to pii_gdpr only.

- filter_pii(text, sensitivity) → calls pii_gdpr via adapter; no legacy implementation.
- apply_pii_replacements → delegates to pii.sanitization (placeholders/generalization).

Single source of truth for detection: apps.knowledge.pii_gdpr. This module does not
contain any detection logic.
"""
from __future__ import annotations

from typing import List, Tuple

from apps.knowledge.pii.sanitization import (
    apply_pii_replacements as _apply_pii_replacements,
    deduplicate_matches_longer_wins,
)

# Legacy contract: (start, end, data_type: str, value: str)
PiiMatch = Tuple[int, int, str, str]


def filter_pii(text: str, sensitivity: str) -> List[PiiMatch]:
    """
    PII detection: runs pii_gdpr pipeline via adapter and returns legacy-format matches.
    No fallback; if pii_gdpr fails, returns empty list (caller may log or handle).
    """
    if not text or not text.strip():
        return []
    try:
        from apps.knowledge.pii.adapter import filter_pii_via_gdpr
        matches = filter_pii_via_gdpr(text, sensitivity)
        return deduplicate_matches_longer_wins(matches)
    except Exception:
        return []


def apply_pii_replacements(
    text: str,
    matches: List[PiiMatch],
    ref_id_by_index: List[str],
    mode: str = "mask",
) -> str:
    """
    Replace PII spans with standardized placeholders [EMAIL_ADDRESS], [PERSON_NAME], etc.
    (mode="mask") or generalization text (mode="generalize"). Replaces from end to start.
    """
    return _apply_pii_replacements(text, matches, ref_id_by_index, mode=mode)
