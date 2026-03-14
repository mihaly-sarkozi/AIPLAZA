# apps/knowledge/pii – Thin compatibility adapter
#
# Source of truth: apps.knowledge.pii_gdpr. This package exposes the legacy API
# (filter_pii, apply_pii_replacements, PiiMatch, PiiConfirmationRequiredError) by
# delegating to pii_gdpr and converting results. No separate detection implementation;
# pipeline and pii_filter both call the adapter only.
from __future__ import annotations

from apps.knowledge.pii.pipeline import (
    filter_pii,
    apply_pii_replacements,
    PiiMatch,
)
from apps.knowledge.pii.policy import PiiConfirmationRequiredError

__all__ = [
    "filter_pii",
    "apply_pii_replacements",
    "PiiMatch",
    "PiiConfirmationRequiredError",
]
