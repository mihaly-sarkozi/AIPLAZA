# backend/core/kernel/deps/registry.py
# Feladat: A runtime-ban regisztrált kernel dependencyk központi registryjét kezeli. Tárolja a fő platform service-eket, repositorykat, factorykat, és FastAPI dependencyként használható getter factorykat ad hozzájuk. A kernel_di_wiring tölti fel, a facade.py pedig public API-ként továbbadja, ezért core/framework szintű dependency registry.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class KernelDependencyRegistry:
    audit_service: Any | None = None
    token_service: Any | None = None
    login_service: Any | None = None
    refresh_service: Any | None = None
    logout_service: Any | None = None
    permission_service: Any | None = None
    tenant_repository: Any | None = None
    user_repository: Any | None = None
    services: dict[str, Any] = field(default_factory=dict)
    repositories: dict[str, Any] = field(default_factory=dict)
    factories: dict[str, Callable[..., Any]] = field(default_factory=dict)


_registry = KernelDependencyRegistry()


def configure_kernel_dependencies(
    *,
    audit_service: Any,
    token_service: Any,
    login_service: Any,
    refresh_service: Any,
    logout_service: Any,
    permission_service: Any,
    tenant_repository: Any,
    user_repository: Any,
) -> None:
    global _registry
    existing_services = dict(_registry.services)
    existing_repositories = dict(_registry.repositories)
    existing_factories = dict(_registry.factories)
    _registry = KernelDependencyRegistry(
        audit_service=audit_service,
        token_service=token_service,
        login_service=login_service,
        refresh_service=refresh_service,
        logout_service=logout_service,
        permission_service=permission_service,
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        services=existing_services,
        repositories=existing_repositories,
        factories=existing_factories,
    )


def _require(name: str, value: Any) -> Any:
    if value is None:
        raise RuntimeError(f"Kernel dependency is not configured: {name}")
    return value


def register_service(name: str, instance: Any) -> None:
    _registry.services[name] = instance


def get_service(name: str) -> Any:
    return _require(f"service:{name}", _registry.services.get(name))


def register_repository(name: str, instance: Any) -> None:
    _registry.repositories[name] = instance


def get_repository(name: str) -> Any:
    return _require(f"repository:{name}", _registry.repositories.get(name))


def register_factory(name: str, factory: Callable[..., Any]) -> None:
    _registry.factories[name] = factory


def get_factory(name: str) -> Callable[..., Any]:
    return _require(f"factory:{name}", _registry.factories.get(name))


def service_dependency(name: str) -> Callable[[], Any]:
    def _dependency():
        return get_service(name)

    _dependency.__name__ = f"get_service__{name.replace('.', '_')}"
    return _dependency


def repository_dependency(name: str) -> Callable[[], Any]:
    def _dependency():
        return get_repository(name)

    _dependency.__name__ = f"get_repository__{name.replace('.', '_')}"
    return _dependency


def factory_dependency(name: str) -> Callable[[Any], Any]:
    def _dependency(request):
        return get_factory(name)(request)

    _dependency.__name__ = f"get_factory__{name.replace('.', '_')}"
    return _dependency


def get_audit_service():
    return _require("audit_service", _registry.audit_service)


def get_token_service():
    return _require("token_service", _registry.token_service)


def get_login_service():
    return _require("login_service", _registry.login_service)


def get_refresh_service():
    return _require("refresh_service", _registry.refresh_service)


def get_logout_service():
    return _require("logout_service", _registry.logout_service)


def get_permission_service():
    return _require("permission_service", _registry.permission_service)


def get_tenant_repository():
    return _require("tenant_repository", _registry.tenant_repository)


def get_user_repository():
    return _require("user_repository", _registry.user_repository)


def get_cache():
    from core.infrastructure.cache import get_cache as _get_cache

    return _get_cache()


__all__ = [
    "configure_kernel_dependencies",
    "factory_dependency",
    "get_audit_service",
    "get_cache",
    "get_factory",
    "get_login_service",
    "get_logout_service",
    "get_permission_service",
    "get_refresh_service",
    "get_repository",
    "get_service",
    "get_tenant_repository",
    "get_token_service",
    "get_user_repository",
    "register_factory",
    "register_repository",
    "register_service",
    "repository_dependency",
    "service_dependency",
]
