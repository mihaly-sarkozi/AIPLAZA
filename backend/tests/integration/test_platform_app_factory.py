from __future__ import annotations

import pytest

from apps import load_enabled_app_modules
from core.platform.bootstrap.manifest import (
    configure_app_modules_loader,
    load_app_manifest,
    load_platform_only_app_manifest,
)
from core.kernel.app_factory import create_app_from_manifests
from core.platform.registry import load_core_platform_manifest

pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def test_platform_app_starts_without_business_modules(monkeypatch):
    configure_app_modules_loader(load_enabled_app_modules)
    monkeypatch.setenv("DISABLED_APP_MODULES", "chat,knowledge")
    app = create_app_from_manifests(
        load_core_platform_manifest(),
        load_app_manifest(),
    )

    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/auth/login" in routes
    assert "/api/auth/me" in routes
    assert "/api/installer/tenant-signup" in routes
    assert "/api/settings" in routes
    assert "/api/platform/domain" in routes
    assert "/api/platform/brand" in routes
    assert "/api/platform/lifecycle" in routes
    assert "/api/health" in routes
    assert "/api/health/live" in routes
    assert "/api/health/ready" in routes
    assert "/api/chat" not in routes
    assert "/api/kb" not in routes


def test_platform_app_starts_with_explicit_platform_only_manifest():
    app = create_app_from_manifests(
        load_core_platform_manifest(),
        load_platform_only_app_manifest(),
    )

    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/auth/login" in routes
    assert "/api/auth/me" in routes
    assert "/api/installer/tenant-signup" in routes
    assert "/api/platform/domain" in routes
    assert "/api/platform/brand" in routes
    assert "/api/platform/lifecycle" in routes
    assert "/api/health" in routes
    assert "/api/health/live" in routes
    assert "/api/health/ready" in routes
    assert "/api/chat" not in routes
    assert "/api/kb" not in routes


def test_platform_manifest_collects_module_lifecycle_hooks():
    manifest = load_core_platform_manifest()
    lifecycle_module = next(module for module in manifest.modules if getattr(module, "key", "") == "platform.lifecycle")

    assert any(getattr(hook, "__name__", "").startswith("_startup") for hook in lifecycle_module.startup_hooks())
    assert any(getattr(hook, "__name__", "").startswith("_shutdown") for hook in lifecycle_module.shutdown_hooks())


def test_platform_manifest_orders_modules_by_registration_dependencies():
    manifest = load_core_platform_manifest()
    keys = [getattr(module, "key", "") for module in manifest.modules]

    assert keys.index("platform.settings") < keys.index("platform.auth")
    assert keys.index("platform.users") < keys.index("platform.tenant")
    assert keys.index("platform.tenant") < keys.index("platform.domain")
