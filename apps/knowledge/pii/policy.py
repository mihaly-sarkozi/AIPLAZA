# apps/knowledge/pii/policy.py
"""
Thin compatibility layer: sensitivity scope (weak/medium/strong) and confirmation error.

- entities_for_sensitivity(sensitivity) → set of legacy type names for that scope.
  Source: pii_gdpr.entity_registry.get_sensitivity_set. Used by pipeline and tests.
- PiiConfirmationRequiredError: exception with detected_types (legacy type strings).

All policy decisions (MASK/KEEP/review) and detection logic live in pii_gdpr.
"""
from __future__ import annotations

from typing import List, Set

from apps.knowledge.pii_gdpr.entity_registry import get_sensitivity_set


def entities_for_sensitivity(sensitivity: str) -> Set[str]:
    """Return the set of legacy entity type names allowed for the given sensitivity."""
    return set(get_sensitivity_set(sensitivity))


class PiiConfirmationRequiredError(Exception):
    """Raised when content contains PII and user confirmation is required (with_confirmation mode)."""

    def __init__(
        self,
        detected_types: List[str],
        counts: dict[str, int] | None = None,
        snippets: List[dict[str, str]] | None = None,
    ) -> None:
        self.detected_types = list(detected_types)
        self.counts = dict(counts) if counts else {}
        self.snippets = list(snippets) if snippets else []
        super().__init__(f"Személyes adatok észlelve: {', '.join(self.detected_types)}")
