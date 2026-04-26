from __future__ import annotations

import importlib

__all__ = [
    "candidate_demo_slug",
    "demo_host_hint",
    "demo_slug_base",
    "demo_trial_expires_at",
    "initial_demo_knowledge_base_name",
    "normalize_demo_locale",
]

_LAZY: dict[str, tuple[str, str]] = {
    name: ("core.extensions.tenant.policies.demo_signup_policy", name)
    for name in __all__
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
