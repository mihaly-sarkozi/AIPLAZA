"""Backward-compat: demo signup név- és locale-szabályok.

Canonical modul: ``core.extensions.tenant.slug.policy``.
"""
from __future__ import annotations

from core.extensions.tenant.slug.policy import (  # noqa: F401
    SUPPORTED_DEMO_LOCALES,
    candidate_demo_slug,
    demo_host_hint,
    demo_slug_base,
    demo_trial_expires_at,
    initial_demo_knowledge_base_name,
    normalize_demo_locale,
)

__all__ = [
    "SUPPORTED_DEMO_LOCALES",
    "candidate_demo_slug",
    "demo_host_hint",
    "demo_slug_base",
    "demo_trial_expires_at",
    "initial_demo_knowledge_base_name",
    "normalize_demo_locale",
]
