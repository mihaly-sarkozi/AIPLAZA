# Ez a fájl a(z) di modul backend logikáját tartalmazza.
from __future__ import annotations

from typing import Any, Callable

from fastapi import Request

from core.kernel.bootstrap.container import get_container


# Ez a függvény kikényszeríti a(z) modul namespace logikáját.
def _require_module_namespace(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized.startswith("module."):
        raise ValueError(f"App dependency must use module.* namespace: {name}")
    return normalized


# Ez a függvény visszaadja a(z) szolgáltatás logikáját.
def get_service(name: str) -> Any:
    return get_container().get_registered_service(_require_module_namespace(name))


# Ez a függvény visszaadja a(z) repository logikáját.
def get_repository(name: str) -> Any:
    return get_container().get_registered_repository(_require_module_namespace(name))


# Ez a függvény visszaadja a(z) factory logikáját.
def get_factory(name: str) -> Callable[..., Any]:
    return get_container().get_registered_factory(_require_module_namespace(name))


# Ez a függvény a(z) module_service_dependency logikáját valósítja meg.
def module_service_dependency(name: str) -> Callable[[], Any]:
    normalized = _require_module_namespace(name)

    # Ez a függvény a(z) dependency logikáját valósítja meg.
    def _dependency():
        return get_service(normalized)

    _dependency.__name__ = f"get_module_service__{normalized.replace('.', '_')}"
    return _dependency


# Ez a függvény a(z) module_repository_dependency logikáját valósítja meg.
def module_repository_dependency(name: str) -> Callable[[], Any]:
    normalized = _require_module_namespace(name)

    # Ez a függvény a(z) dependency logikáját valósítja meg.
    def _dependency():
        return get_repository(normalized)

    _dependency.__name__ = f"get_module_repository__{normalized.replace('.', '_')}"
    return _dependency


# Ez a függvény a(z) module_factory_dependency logikáját valósítja meg.
def module_factory_dependency(name: str) -> Callable[[Request], Any]:
    normalized = _require_module_namespace(name)

    # Ez a függvény a(z) dependency logikáját valósítja meg.
    def _dependency(request: Request):
        return get_factory(normalized)(request)

    _dependency.__name__ = f"get_module_factory__{normalized.replace('.', '_')}"
    return _dependency


__all__ = [
    "get_service",
    "get_repository",
    "get_factory",
    "module_service_dependency",
    "module_repository_dependency",
    "module_factory_dependency",
]
