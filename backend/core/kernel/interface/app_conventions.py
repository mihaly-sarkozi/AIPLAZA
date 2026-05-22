# backend/core/kernel/interface/app_conventions.py
# Feladat: App modulok név- és struktúrakonvencióit definiálja. Tartalmazza a kötelező, ajánlott és opcionális fájlútvonal mintákat, valamint a module key, route tag és hook név helper függvényeket. Core public convention réteg, amelyet app modulok és architektúra tesztek használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

"""Official conventions for backend app modules."""

APP_MODULE_REQUIRED_PATHS: tuple[str, ...] = (
    "module.py",
    "web/module.tsx",
)

APP_MODULE_RECOMMENDED_PATHS: tuple[str, ...] = (
    "dependencies.py",
    "router/__init__.py",
    "router/{module_name}_router.py",
    "service/__init__.py",
    "service/{module_name}_service.py",
)

APP_MODULE_OPTIONAL_PATHS: tuple[str, ...] = (
    "container/__init__.py",
    "container/{module_name}_container.py",
    "domain/__init__.py",
    "dto.py",
    "hooks.py",
    "infrastructure.py",
    "models/__init__.py",
    "policies.py",
    "ports/__init__.py",
    "repositories/__init__.py",
    "runtime.py",
    "tenant_hooks.py",
    "tests/",
    "web/",
    "workflows.py",
)


def _normalize_module_name(module_name: str) -> str:
    normalized = str(module_name or "").strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("module_name must not be empty")
    return normalized


def module_key(module_name: str) -> str:
    return f"app.{_normalize_module_name(module_name)}"


def module_route_tag(module_name: str) -> str:
    return _normalize_module_name(module_name)


def module_hook_name(module_name: str, hook_name: str) -> str:
    normalized_hook = str(hook_name or "").strip().lower().replace(" ", "_")
    if not normalized_hook:
        raise ValueError("hook_name must not be empty")
    return f"{module_key(module_name)}.{normalized_hook}"


__all__ = [
    "APP_MODULE_OPTIONAL_PATHS",
    "APP_MODULE_RECOMMENDED_PATHS",
    "APP_MODULE_REQUIRED_PATHS",
    "module_hook_name",
    "module_key",
    "module_route_tag",
]
