# Ez a fájl a(z) core/extensions/tenant/middleware csomag exportjait és inicializálási pontjait fogja össze.
from importlib import import_module


def __getattr__(name: str):
    if name in {"invalidate_domain2tenant_cache", "invalidate_tenant_cache"}:
        cache = import_module("core.extensions.tenant.cache")

        return getattr(cache, name)
    if name in {"TenantResolutionService", "warm_tenant_cache"}:
        resolution_service = import_module("core.extensions.tenant.routing.resolution")

        return getattr(resolution_service, name)
    if name == "TenantMiddleware":
        from core.extensions.tenant.middleware.tenant_middleware import TenantMiddleware

        return TenantMiddleware
    raise AttributeError(name)


__all__ = [
    "TenantMiddleware",
    "TenantResolutionService",
    "warm_tenant_cache",
    "invalidate_tenant_cache",
    "invalidate_domain2tenant_cache",
]
