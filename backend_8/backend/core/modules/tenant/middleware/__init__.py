# backend/core/modules/tenant/middleware/__init__.py
# Feladat: A tenant middleware csomag exportfelülete és részben kompatibilitási importpontja. A tenant ASGI middleware és request state helper típusait adja tovább a kernel HTTP pipeline számára. Tenant request integrációs belépési pont.
# Sárközi Mihály - 2026.05.21

from importlib import import_module


def __getattr__(name: str):
    if name in {"invalidate_domain2tenant_cache", "invalidate_tenant_cache"}:
        cache = import_module("core.modules.tenant.cache")

        return getattr(cache, name)
    if name in {"TenantResolutionService", "warm_tenant_cache"}:
        resolution_service = import_module("core.modules.tenant.routing.resolution")

        return getattr(resolution_service, name)
    if name == "TenantMiddleware":
        from core.modules.tenant.middleware.tenant_middleware import TenantMiddleware

        return TenantMiddleware
    raise AttributeError(name)


__all__ = [
    "TenantMiddleware",
    "TenantResolutionService",
    "warm_tenant_cache",
    "invalidate_tenant_cache",
    "invalidate_domain2tenant_cache",
]
