from __future__ import annotations

import re

import pytest

from apps.registry import load_app_modules
from core.kernel.app.app_factory import create_app_from_manifest
from core.kernel.http import middleware_registration
from core.kernel.app.app_manifest import AppManifest
from core.kernel.config.config_loader import get_settings

pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def _create_test_app(module_loader):
    runtime_manifest = AppManifest.load_core().add_modules(module_loader())
    return create_app_from_manifest(runtime_manifest, settings=get_settings())


def test_platform_app_starts_without_business_modules(monkeypatch):
    monkeypatch.setenv("DISABLED_APP_MODULES", "chat,kb")
    app = _create_test_app(load_app_modules)

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
    app = _create_test_app(tuple)

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


def test_manifest_collects_module_lifecycle_hooks():
    manifest = AppManifest.load_core()
    lifecycle_module = next(module for module in manifest.modules if getattr(module, "key", "") == "platform.lifecycle")

    assert any(getattr(hook, "__name__", "").startswith("_startup") for hook in lifecycle_module.startup_hooks())
    assert any(getattr(hook, "__name__", "").startswith("_shutdown") for hook in lifecycle_module.shutdown_hooks())


def test_manifest_orders_modules_by_registration_dependencies():
    manifest = AppManifest.load_core()
    keys = [getattr(module, "key", "") for module in manifest.modules]

    assert keys.index("platform.settings") < keys.index("platform.auth")
    assert keys.index("platform.users") < keys.index("platform.tenant")
    assert keys.index("platform.tenant") < keys.index("platform.domain")


def test_platform_app_disables_openapi_docs_in_prod(monkeypatch):
    current_settings = get_settings()
    monkeypatch.setattr(current_settings, "openapi_enabled", False, raising=False)
    app = _create_test_app(tuple)

    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/docs" not in routes
    assert "/redoc" not in routes
    assert "/openapi.json" not in routes


def test_cors_origin_regex_rejects_non_tenant_origins(monkeypatch):
    monkeypatch.setattr(middleware_registration.settings, "tenant_base_domain", "app.test", raising=False)
    regex = middleware_registration._build_cors_origin_regex()

    assert re.match(regex, "https://demo.app.test")
    assert re.match(regex, "https://app.test")
    assert not re.match(regex, "https://app.test.evil.com")
    assert not re.match(regex, "https://evil-app.test")
    assert not re.match(regex, "https://evil.com")
