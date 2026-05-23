# backend/core/modules/tenant/models/__init__.py
# Feladat: A tenant public schema ORM modellek lazy exportfelülete. TenantORM, TenantConfigORM és TenantDomainORM modelleket ad tovább repositoryk és migrációk számára. Tenant model csomag belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["TenantORM", "TenantConfigORM", "TenantDomainORM"]

_LAZY: dict[str, tuple[str, str]] = {
    "TenantORM": ("core.modules.tenant.models.tenant_orm", "TenantORM"),
    "TenantConfigORM": ("core.modules.tenant.models.tenant_config_orm", "TenantConfigORM"),
    "TenantDomainORM": ("core.modules.tenant.models.tenant_domain_orm", "TenantDomainORM"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
