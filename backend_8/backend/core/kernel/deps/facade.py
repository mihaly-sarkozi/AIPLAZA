# backend/core/kernel/deps/facade.py
# Feladat: A kernel dependency rendszer stabil public facade-ja. Egy helyről exportálja a registry alapú service/repository/factory gettereket, register függvényeket és a tenant HTTP dependencyket lazy importtal. Routerek, middleware-ek, tesztek és runtime wiring használják, ezért ez a dependency hozzáférés általános keretrendszer-belépési pontja.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.deps.registry import (
    configure_kernel_dependencies,
    factory_dependency,
    get_audit_service,
    get_cache,
    get_factory,
    get_login_service,
    get_logout_service,
    get_permission_service,
    get_refresh_service,
    get_repository,
    get_service,
    get_tenant_repository,
    get_token_service,
    get_user_repository,
    register_factory,
    register_repository,
    register_service,
    repository_dependency,
    service_dependency,
)

_HTTP_EXPORTS = {
    "OptionalTenantContextDep",
    "RequestTenantContext",
    "RequiredTenantContextDep",
    "get_tenant_context",
    "require_tenant_context",
    "set_tenant_context_from_request",
}


def __getattr__(name: str):
    if name in _HTTP_EXPORTS:
        from core.kernel.http.tenant_dependencies import __dict__ as http_exports

        return http_exports[name]
    raise AttributeError(name)


__all__ = [
    "configure_kernel_dependencies",
    "register_service",
    "get_service",
    "register_repository",
    "get_repository",
    "register_factory",
    "get_factory",
    "service_dependency",
    "repository_dependency",
    "factory_dependency",
    "RequestTenantContext",
    "OptionalTenantContextDep",
    "RequiredTenantContextDep",
    "get_cache",
    "get_tenant_context",
    "require_tenant_context",
    "set_tenant_context_from_request",
    "get_audit_service",
    "get_token_service",
    "get_login_service",
    "get_refresh_service",
    "get_logout_service",
    "get_permission_service",
    "get_tenant_repository",
    "get_user_repository",
]
