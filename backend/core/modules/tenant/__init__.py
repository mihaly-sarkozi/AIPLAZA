# backend/core/modules/tenant/__init__.py
# Feladat: A tenant modul lazy exportfelületét adja. DTO-kat, portokat, repositorykat, schema/sign-up/provisioning segédeket és a TenantCoreModule-t kérésre importálja, hogy a csomag betöltése ne húzza be az egész tenant stack-et. Core platform tenant modul belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["TenantCoreModule"]


def __getattr__(name: str):
    if name == "TenantCoreModule":
        return getattr(importlib.import_module("core.modules.tenant.tenant"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
