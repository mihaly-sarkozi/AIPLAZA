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
    "TenantResolutionService": ("core.extensions.tenant.routing.resolution", "TenantResolutionService"),
    "warm_tenant_cache": ("core.extensions.tenant.routing.resolution", "warm_tenant_cache"),
    "apply_tenant_snapshot": ("core.extensions.tenant.routing.request_state", "apply_tenant_snapshot"),
    "initialize_tenant_state": ("core.extensions.tenant.routing.request_state", "initialize_tenant_state"),
    "tenant_from_json": ("core.extensions.tenant.routing.snapshot_codec", "tenant_from_json"),
    "tenant_to_json": ("core.extensions.tenant.routing.snapshot_codec", "tenant_to_json"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
