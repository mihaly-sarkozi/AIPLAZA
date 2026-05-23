# backend/core/kernel/http/app_dependencies.py
# Feladat: FastAPI request szintű module dependency providereket ad. A module.* kulcsokat a requesthez kötött AppContainerből vagy fallbackként a globális containerből oldja fel, így routerek tiszta dependency függvényeket használhatnak. Core HTTP adapter, amely a DI registryt köti össze FastAPI endpointokkal.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any, Callable

from fastapi import Request

from core.kernel.app.app_container import get_container


def get_module_service(name: str, request: Request | None = None) -> Any:
    return _container_from_request(request).get_registered_service(_require_module_namespace(name))


def get_module_repository(name: str, request: Request | None = None) -> Any:
    return _container_from_request(request).get_registered_repository(_require_module_namespace(name))


def get_module_factory(name: str, request: Request | None = None) -> Callable[..., Any]:
    return _container_from_request(request).get_registered_factory(_require_module_namespace(name))


def module_service_dependency(name: str) -> Callable[[Request], Any]:
    normalized = _require_module_namespace(name)

    def _dependency(request: Request):
        return get_module_service(normalized, request)

    _dependency.__name__ = f"get_module_service__{normalized.replace('.', '_')}"
    return _dependency


def module_repository_dependency(name: str) -> Callable[[Request], Any]:
    normalized = _require_module_namespace(name)

    def _dependency(request: Request):
        return get_module_repository(normalized, request)

    _dependency.__name__ = f"get_module_repository__{normalized.replace('.', '_')}"
    return _dependency


def module_factory_dependency(name: str) -> Callable[[Request], Any]:
    normalized = _require_module_namespace(name)

    def _dependency(request: Request):
        return get_module_factory(normalized, request)(request)

    _dependency.__name__ = f"get_module_factory__{normalized.replace('.', '_')}"
    return _dependency


def _require_module_namespace(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized.startswith("module."):
        raise ValueError(f"App dependency must use module.* namespace: {name}")
    return normalized


def _container_from_request(request: Request | None = None):
    if request is not None:
        container = getattr(request.app.state, "container", None)
        if container is not None:
            return container
    return get_container()


__all__ = [
    "get_module_factory",
    "get_module_repository",
    "get_module_service",
    "module_factory_dependency",
    "module_repository_dependency",
    "module_service_dependency",
]
