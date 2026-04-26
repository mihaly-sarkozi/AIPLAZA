# Ez a fájl a(z) di modul backend logikáját tartalmazza.
"""
Gyoker szintu DI belepesi pont.

A pure registry implementacio a `core.kernel.dependency_registry`,
a FastAPI-specifikus dependency reteg pedig a `core.kernel.http_dependencies`
modulban van. Az alkalmazas bootstrap csak regisztralja a konkret
szolgaltatasokat a kernel registry-be.
"""

from collections.abc import Callable
from typing import Any

from core.extensions.tenant.context.tenant_context import current_tenant_schema

from core.kernel.di import (  # noqa: F401
    configure_kernel_dependencies,
    get_audit_service,
    get_cache,
    get_factory,
    get_login_service,
    get_logout_service,
    get_permission_service,
    get_repository,
    get_refresh_service,
    get_service,
    get_tenant_repository,
    get_token_service,
    get_user_repository,
    register_factory,
    register_repository,
    register_service,
    factory_dependency,
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
        from core.kernel.http_dependencies import __dict__ as http_exports

        return http_exports[name]
    raise AttributeError(name)


def run_with_tenant_schema(tenant_slug: str | None, callback: Callable[..., Any], *args, **kwargs) -> Any:
    token = current_tenant_schema.set((tenant_slug or "").strip() or None)
    try:
        return callback(*args, **kwargs)
    finally:
        current_tenant_schema.reset(token)

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
    "run_with_tenant_schema",
    "get_audit_service",
    "get_login_service",
    "get_logout_service",
    "get_permission_service",
    "get_refresh_service",
    "get_token_service",
    "get_tenant_repository",
    "get_user_repository",
]
