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
        "core.extensions.tenant.context.request_tenant_context",
        "RequestTenantContext",
    ),
    "build_request_tenant_context": (
        "core.extensions.tenant.context.request_tenant_context",
        "build_request_tenant_context",
    ),
    "validate_required_tenant_context": (
        "core.extensions.tenant.context.request_tenant_context",
        "validate_required_tenant_context",
    ),
    "current_tenant_schema": (
        "core.extensions.tenant.context.tenant_context",
        "current_tenant_schema",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
