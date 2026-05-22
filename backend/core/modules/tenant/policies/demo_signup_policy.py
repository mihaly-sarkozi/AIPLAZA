# backend/core/modules/tenant/policies/demo_signup_policy.py
# Feladat: Kompatibilitási importútvonal a demo sign-up slug és locale policyhoz. Az új canonical implementáció a slug/policy.py alatt él, ez a fájl régi importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: demo signup név- és locale-szabályok.

Canonical modul: ``core.modules.tenant.slug.policy``.
"""
from __future__ import annotations

from core.modules.tenant.slug.policy import (  # noqa: F401
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
