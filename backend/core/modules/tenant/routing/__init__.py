# backend/core/modules/tenant/routing/__init__.py
# Feladat: A tenant routing csomag exportfelülete. Host resolution, snapshot codec és request state helper funkciókat ad tovább a middleware és tesztek számára. Tenant routing integrációs belépési pont.
# Sárközi Mihály - 2026.05.21

"""Tenant routing / feloldás: host → slug, snapshot szerializáció, request state.

Nem HTTP-specifikus middleware: a ``middleware.TenantMiddleware`` csak erre épít.
Extension point: ``TenantResolutionService`` + routing policy injektálás.
"""
from __future__ import annotations

import importlib

__all__ = [
    "TenantResolutionService",
    "apply_tenant_snapshot",
    "initialize_tenant_state",
    "tenant_from_json",
    "tenant_to_json",
    "warm_tenant_cache",
]

_LAZY: dict[str, tuple[str, str]] = {
    "TenantResolutionService": ("core.modules.tenant.routing.resolution", "TenantResolutionService"),
    "warm_tenant_cache": ("core.modules.tenant.routing.resolution", "warm_tenant_cache"),
    "apply_tenant_snapshot": ("core.modules.tenant.routing.request_state", "apply_tenant_snapshot"),
    "initialize_tenant_state": ("core.modules.tenant.routing.request_state", "initialize_tenant_state"),
    "tenant_from_json": ("core.modules.tenant.routing.snapshot_codec", "tenant_from_json"),
    "tenant_to_json": ("core.modules.tenant.routing.snapshot_codec", "tenant_to_json"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
