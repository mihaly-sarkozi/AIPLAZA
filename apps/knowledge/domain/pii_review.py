# apps/knowledge/domain/pii_review.py
"""PII review flow: decision model and payload helpers."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

# PiiMatch = (start, end, data_type: str, value: str)


class PiiReviewDecision(str, Enum):
    """User decision when PII was detected and confirmation is required."""

    MASK_ALL = "mask_all"
    """Mask all detected PII and store sanitized content."""

    KEEP_ROLE_BASED_EMAILS = "keep_role_based_emails"
    """Keep role-based emails (e.g. info@, support@) unmasked; mask the rest."""

    REJECT_UPLOAD = "reject_upload"
    """Do not store; reject the upload."""

    CONTINUE_SANITIZED = "continue_sanitized"
    """Same as mask_all: continue with sanitized content (legacy confirm_pii=True)."""


def build_pii_review_payload(
    matches: List[tuple],
    max_snippets_per_type: int = 3,
    preview_max_len: int = 40,
) -> tuple[List[str], Dict[str, int], List[Dict[str, str]]]:
    """
    From legacy PiiMatch list (start, end, data_type, value) build:
    - detected_types: unique type names
    - counts: type -> count
    - snippets: list of {"type": str, "preview": str} (redacted preview)
    """
    if not matches:
        return [], {}, []

    type_counts: Dict[str, int] = {}
    type_seen: Dict[str, int] = {}
    snippets: List[Dict[str, str]] = []

    for m in matches:
        if len(m) < 4:
            continue
        start, end, data_type, value = m[0], m[1], m[2], m[3]
        data_type = (data_type or "").strip()
        value = (value or "").strip()
        type_counts[data_type] = type_counts.get(data_type, 0) + 1

        if len(snippets) >= len(type_counts) * max_snippets_per_type:
            continue
        n = type_seen.get(data_type, 0)
        if n >= max_snippets_per_type:
            continue
        type_seen[data_type] = n + 1
        preview = _redact_preview(data_type, value, preview_max_len)
        snippets.append({"type": data_type, "preview": preview})

    detected_types = sorted(type_counts.keys())
    return detected_types, type_counts, snippets


def _redact_preview(entity_type: str, value: str, max_len: int) -> str:
    """Produce a short redacted preview for UI (avoid leaking full PII)."""
    if not value:
        return ""
    t = (entity_type or "").lower()
    v = value.strip()
    if len(v) <= 3:
        return "***"
    if "email" in t or t == "email":
        if "@" in v:
            local, _, domain = v.partition("@")
            if local:
                head = local[0] + "***"
            else:
                head = "***"
            return f"{head}@{domain}"[:max_len]
    if "phone" in t or "telefon" in t:
        return v[:2] + "***" + v[-2:] if len(v) > 4 else "***"
    if "név" in t or "person" in t or "name" in t:
        return (v[0] + "***")[:max_len]
    return v[:1] + "***" if len(v) > 1 else "***"
