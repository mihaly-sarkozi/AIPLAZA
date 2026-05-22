# backend/core/modules/tenant/context/__init__.py
# Feladat: A tenant context csomag exportfelülete. Az aktuális tenant schema ContextVar helperjeit és a request tenant context DTO-t adja tovább a DB, middleware és app rétegek számára. Tenant request/runtime context belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "RequestTenantContext",
    "build_request_tenant_context",
    "current_tenant_schema",
    "validate_required_tenant_context",
]

_LAZY: dict[str, tuple[str, str]] = {
    "RequestTenantContext": (
        "core.modules.tenant.context.request_tenant_context",
        "RequestTenantContext",
    ),
    "build_request_tenant_context": (
        "core.modules.tenant.context.request_tenant_context",
        "build_request_tenant_context",
    ),
    "validate_required_tenant_context": (
        "core.modules.tenant.context.request_tenant_context",
        "validate_required_tenant_context",
    ),
    "current_tenant_schema": (
        "core.modules.tenant.context.tenant_context",
        "current_tenant_schema",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
