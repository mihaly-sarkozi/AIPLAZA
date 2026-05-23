# backend/core/modules/tenant/tokens/__init__.py
# Feladat: A tenant token csomag exportfelülete. A demo login JWT token service-t adja tovább a signup orchestrator és kompatibilitási importok számára. Tenant token helper belépési pont.
# Sárközi Mihály - 2026.05.21

"""Demo bejelentkezési JWT / aláírás – platform TokenService-re épül."""
from __future__ import annotations

import importlib

__all__ = ["DemoLoginTokenService"]


def __getattr__(name: str):
    if name == "DemoLoginTokenService":
        return getattr(importlib.import_module("core.modules.tenant.tokens.demo_jwt"), "DemoLoginTokenService")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
