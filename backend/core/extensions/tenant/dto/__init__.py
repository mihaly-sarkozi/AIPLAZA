# Ez a fájl a(z) core/extensions/tenant/dto csomag exportjait és inicializálási pontjait fogja össze.
"""Tenant DTO-k: lazy re-export."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.extensions.tenant.dto.tenant import Tenant
    from core.extensions.tenant.dto.tenant_config import TenantConfig
    from core.extensions.tenant.dto.tenant_domain import TenantDomain
    from core.extensions.tenant.dto.tenant_domain_info import TenantDomainInfo
    from core.extensions.tenant.dto.tenant_snapshot import TenantSnapshot
    from core.extensions.tenant.dto.tenant_status import TenantStatus

_LAZY: dict[str, tuple[str, str]] = {
    "Tenant": ("core.extensions.tenant.dto.tenant", "Tenant"),
    "TenantConfig": ("core.extensions.tenant.dto.tenant_config", "TenantConfig"),
    "TenantDomain": ("core.extensions.tenant.dto.tenant_domain", "TenantDomain"),
    "TenantDomainInfo": ("core.extensions.tenant.dto.tenant_domain_info", "TenantDomainInfo"),
    "TenantSnapshot": ("core.extensions.tenant.dto.tenant_snapshot", "TenantSnapshot"),
    "TenantStatus": ("core.extensions.tenant.dto.tenant_status", "TenantStatus"),
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
