"""Demo / tenant slug generálás és foglalás (policy + idempotens reservation)."""
from __future__ import annotations

import importlib

__all__ = [
    "SUPPORTED_DEMO_LOCALES",
    "DemoSlugReserver",
    "candidate_demo_slug",
    "demo_host_hint",
    "demo_slug_base",
    "demo_trial_expires_at",
    "initial_demo_knowledge_base_name",
    "normalize_demo_locale",
]

_LAZY_POLICY = "core.extensions.tenant.slug.policy"
_LAZY_RES = "core.extensions.tenant.slug.reservation"


def __getattr__(name: str):
    if name == "DemoSlugReserver":
        return getattr(importlib.import_module(_LAZY_RES), "DemoSlugReserver")
    mod = importlib.import_module(_LAZY_POLICY)
    if hasattr(mod, name):
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
