# apps/knowledge/application/pii_filter.py
"""
PII filtering and replacement for the application layer.

Single source of truth: apps.knowledge.pii_gdpr. This module re-exports from the
thin pii compatibility layer (pii.pipeline, pii.sanitization, pii.policy).
No detection logic here; all detection runs via pii → pii_gdpr.
"""
from __future__ import annotations

from apps.knowledge.pii import (
    filter_pii,
    apply_pii_replacements,
    PiiMatch,
    PiiConfirmationRequiredError,
)
from apps.knowledge.pii.sanitization import apply_pii_replacements_with_decisions

__all__ = [
    "filter_pii",
    "apply_pii_replacements",
    "apply_pii_replacements_with_decisions",
    "PiiMatch",
    "PiiConfirmationRequiredError",
]
