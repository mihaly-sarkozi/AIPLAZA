from __future__ import annotations

import importlib

__all__ = ["TenantORM", "TenantConfigORM", "TenantDomainORM"]

_LAZY: dict[str, tuple[str, str]] = {
    "TenantORM": ("core.extensions.tenant.models.tenant_orm", "TenantORM"),
    "TenantConfigORM": ("core.extensions.tenant.models.tenant_config_orm", "TenantConfigORM"),
    "TenantDomainORM": ("core.extensions.tenant.models.tenant_domain_orm", "TenantDomainORM"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
