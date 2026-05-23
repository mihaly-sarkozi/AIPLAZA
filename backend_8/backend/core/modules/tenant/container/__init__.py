# backend/core/modules/tenant/container/__init__.py
# Feladat: A tenant container csomag exportfelülete. A TenantContainer-t adja tovább a runtime assembly számára, ahol repositoryk, schema manager és sign-up/provisioning use case-ek állnak össze. Vékony integrációs belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["TenantExtensionContainer", "build_tenant_extension"]

_LAZY: dict[str, tuple[str, str]] = {
    "TenantExtensionContainer": (
        "core.modules.tenant.container.tenant_container",
        "TenantExtensionContainer",
    ),
    "build_tenant_extension": (
        "core.modules.tenant.container.tenant_container",
        "build_tenant_extension",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
