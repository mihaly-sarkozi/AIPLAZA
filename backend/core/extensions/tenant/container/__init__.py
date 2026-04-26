from __future__ import annotations

import importlib

__all__ = ["TenantExtensionContainer", "build_tenant_extension"]

_LAZY: dict[str, tuple[str, str]] = {
    "TenantExtensionContainer": (
        "core.extensions.tenant.container.tenant_container",
        "TenantExtensionContainer",
    ),
    "build_tenant_extension": (
        "core.extensions.tenant.container.tenant_container",
        "build_tenant_extension",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
