from __future__ import annotations

import builtins
import importlib
from contextlib import contextmanager

import pytest

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]


@contextmanager
def forbid_imports(*roots: str):
    original_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".", 1)[0]
        if root in roots:
            raise AssertionError(f"forbidden import during architecture smoke test: {name}")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded
    try:
        yield
    finally:
        builtins.__import__ = original_import


def test_platform_interface_imports_without_fastapi_or_sqlalchemy() -> None:
    with forbid_imports("fastapi", "sqlalchemy"):
        interface = importlib.import_module("core.kernel.interface")

    assert interface.__all__ == [
        "BaseAppModule",
        "ModuleContext",
        "RouteRegistration",
    ]


def test_platform_interface_graph_imports_without_cycles() -> None:
    with forbid_imports("fastapi", "sqlalchemy"):
        interface = importlib.import_module("core.kernel.interface")
        modules = importlib.import_module("core.kernel.interface")
        app_manifest = importlib.import_module("core.kernel.app.app_manifest")

    assert modules.BaseAppModule is interface.BaseAppModule
    assert modules.ModuleContext is interface.ModuleContext
    assert hasattr(app_manifest, "AppManifest")


def test_platform_services_import_without_sqlalchemy() -> None:
    with forbid_imports("sqlalchemy"):
        modules = [
            importlib.import_module("core.modules.brand.domain"),
            importlib.import_module("core.modules.brand.service.brand_service"),
            importlib.import_module("core.kernel.domain.services"),
            importlib.import_module("core.modules.settings.service.settings_service"),
            importlib.import_module("core.kernel.lifecycle.lifecycle_service"),
        ]

    assert len(modules) == 5
