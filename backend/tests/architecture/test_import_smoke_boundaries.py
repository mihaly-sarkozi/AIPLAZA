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


def test_platform_contract_imports_without_fastapi_or_sqlalchemy() -> None:
    with forbid_imports("fastapi", "sqlalchemy"):
        contract = importlib.import_module("core.platform.contract")

    assert contract.__all__ == [
        "AppModule",
        "BootstrapHook",
        "LifecycleHook",
        "ModuleContext",
        "RouteRegistration",
        "TenantSchemaRegistrar",
    ]


def test_platform_contract_graph_imports_without_cycles() -> None:
    with forbid_imports("fastapi", "sqlalchemy"):
        contract = importlib.import_module("core.platform.contract")
        composition = importlib.import_module("core.platform.composition")
        manifest = importlib.import_module("core.platform.manifest")

    assert composition.AppModule is contract.AppModule
    assert composition.ModuleContext is contract.ModuleContext
    assert hasattr(manifest, "PlatformManifest")
    assert hasattr(manifest, "AppManifest")


def test_platform_services_import_without_sqlalchemy() -> None:
    with forbid_imports("sqlalchemy"):
        modules = [
            importlib.import_module("core.platform.brand.services"),
            importlib.import_module("core.platform.domain.services"),
            importlib.import_module("core.platform.settings.services"),
            importlib.import_module("core.platform.lifecycle.services"),
        ]

    assert len(modules) == 4
