# backend/core/modules/tenant/dto/__init__.py
# Feladat: A tenant DTO csomag lazy exportfelülete. Tenant, config, domain, domain info, snapshot és status modelleket ad tovább egységes importpontból. Vékony adatcontract belépési pont.
# Sárközi Mihály - 2026.05.21

"""Tenant DTO-k: lazy re-export."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.modules.tenant.dto.tenant import Tenant
    from core.modules.tenant.dto.tenant_config import TenantConfig
    from core.modules.tenant.dto.tenant_domain import TenantDomain
    from core.modules.tenant.dto.tenant_domain_info import TenantDomainInfo
    from core.modules.tenant.dto.tenant_snapshot import TenantSnapshot
    from core.modules.tenant.dto.tenant_status import TenantStatus

_LAZY: dict[str, tuple[str, str]] = {
    "Tenant": ("core.modules.tenant.dto.tenant", "Tenant"),
    "TenantConfig": ("core.modules.tenant.dto.tenant_config", "TenantConfig"),
    "TenantDomain": ("core.modules.tenant.dto.tenant_domain", "TenantDomain"),
    "TenantDomainInfo": ("core.modules.tenant.dto.tenant_domain_info", "TenantDomainInfo"),
    "TenantSnapshot": ("core.modules.tenant.dto.tenant_snapshot", "TenantSnapshot"),
    "TenantStatus": ("core.modules.tenant.dto.tenant_status", "TenantStatus"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        module_path, attr = _LAZY[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(name)


__all__ = [
    "Tenant",
    "TenantConfig",
    "TenantDomain",
    "TenantDomainInfo",
    "TenantSnapshot",
    "TenantStatus",
]
