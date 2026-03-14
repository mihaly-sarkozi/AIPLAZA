# apps/knowledge/application/pii_filter.py
"""
PII filtering and replacement for the application layer.

Single source of truth: pii_gdpr. Detection runs only via the pii adapter (pii_gdpr pipeline).
No legacy fallback; if the adapter fails, filter_pii returns an empty list.
"""
from __future__ import annotations

from typing import List, Tuple

from apps.knowledge.pii.adapter import filter_pii_via_gdpr
from apps.knowledge.pii.sanitization import (
    apply_pii_replacements as _apply_pii_replacements,
    deduplicate_matches_longer_wins,
)
from apps.knowledge.pii.policy import PiiConfirmationRequiredError

# Legacy format: (start, end, data_type: str, value: str)
PiiMatch = Tuple[int, int, str, str]


def filter_pii(text: str, sensitivity: str) -> List[PiiMatch]:
    """
    PII detection via pii_gdpr (adapter). Returns [(start, end, data_type, value), ...].
    On adapter failure returns [] (no legacy path).
    """
    if not text or not text.strip():
        return []
    try:
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
    Replace detections with standard placeholders ([EMAIL_ADDRESS], [PERSON_NAME], …)
    (mode="mask") or generalization text (mode="generalize"). Replaces from end to start.
    """
    return _apply_pii_replacements(text, matches, ref_id_by_index, mode=mode)


__all__ = [
    "filter_pii",
    "apply_pii_replacements",
    "PiiMatch",
    "PiiConfirmationRequiredError",
]
