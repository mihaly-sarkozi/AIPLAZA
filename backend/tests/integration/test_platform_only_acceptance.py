from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from core.platform.bootstrap.manifest import load_platform_only_app_manifest
from core.kernel.bootstrap.container import get_container
from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep
from core.kernel.app_factory import create_app_from_manifests
from core.kernel.config.config_loader import settings
from core.platform.registry import load_core_platform_manifest
from core.platform.auth.auth_dependencies import get_current_user, require_permission
from core.platform.permissions.permission_service import PermissionService

pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def _demo_snapshot():
    from core.extensions.tenant.dto import TenantConfig, TenantDomainInfo, TenantSnapshot, TenantStatus

    return TenantSnapshot(
        tenant_id=1,
        slug="demo",
        name="Demo",
        created_at=datetime.now(timezone.utc),
        security_version=0,
        status=TenantStatus(tenant_id=1, slug="demo", is_active=True),
        config=TenantConfig(
            tenant_id=1,
            slug="demo",
            package="free",
            feature_flags={},
            limits={},
        ),
        domain=TenantDomainInfo(
            request_host=f"demo.{settings.tenant_base_domain}",
            resolved_host=f"demo.{settings.tenant_base_domain}",
            is_custom_domain=False,
            verified_at=None,
        ),
    )


def _build_platform_only_app():
    return create_app_from_manifests(
        load_core_platform_manifest(),
        load_platform_only_app_manifest(),
    )


def _tenant_repo_patch_stack():
    container = get_container(load_platform_only_app_manifest)
    tenant_repo = container.get_tenant_repository()
    demo_snapshot = _demo_snapshot()
    return ExitStack(), tenant_repo, demo_snapshot


def test_platform_only_routes_are_available_without_business_modules():
    app = _build_platform_only_app()
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/auth/login" in routes
    assert "/api/installer/tenant-signup" in routes
    assert "/api/platform/domain" in routes
    assert "/api/platform/brand" in routes
    assert "/api/platform/lifecycle" in routes
    assert "/api/health" in routes
    assert "/api/health/live" in routes
    assert "/api/health/ready" in routes
    assert "/api/metrics" in routes
    assert "/api/chat" not in routes
    assert "/api/kb" not in routes


def test_platform_only_tenant_middleware_resolves_platform_subdomain():
    """Tenant opcionális health útvonal: a hostnak az install engedélyezett bázis domainnek kell lennie (pl. lvh.me)."""
    app = _build_platform_only_app()
    stack, tenant_repo, demo_snapshot = _tenant_repo_patch_stack()
    with stack:
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=None))
        stack.enter_context(
            patch.object(
                tenant_repo,
                "get_snapshot_by_slug",
                side_effect=lambda slug: demo_snapshot if slug == "demo" else None,
            )
        )
        client = TestClient(app, base_url=f"http://{settings.tenant_base_domain}")
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_platform_only_metrics_endpoint_is_tenant_optional():
    app = _build_platform_only_app()
    stack, tenant_repo, _demo_snapshot_unused = _tenant_repo_patch_stack()
    with stack:
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=None))
        client = TestClient(app, base_url=f"http://{settings.tenant_base_domain}")
        response = client.get("/api/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "# TYPE aiplaza_metric_count counter" in response.text


def test_platform_only_tenant_middleware_rejects_unknown_platform_subdomain_for_api():
    app = _build_platform_only_app()
    router = APIRouter()

    @router.get("/platform-only-tenant-check")
    def _tenant_check(tenant: RequiredTenantContextDep):
        return {"tenant": tenant.slug}

    app.include_router(router, prefix="/api")
    stack, tenant_repo, _demo_snapshot_unused = _tenant_repo_patch_stack()
    with stack:
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=None))
        stack.enter_context(patch.object(tenant_repo, "get_snapshot_by_slug", return_value=None))
        client = TestClient(app, base_url=f"http://missing.{settings.tenant_base_domain}")
        response = client.get("/api/platform-only-tenant-check")

    assert response.status_code == 404
    assert "Ismeretlen vagy nem létező tenant" in response.json()["detail"]


def test_platform_only_auth_base_returns_401_without_user():
    app = _build_platform_only_app()
    router = APIRouter()

    @router.get("/platform-only-auth-check")
    def _auth_check(current_user: User = Depends(get_current_user)):
        return {"user_id": current_user.id}

    app.include_router(router, prefix="/api")
    stack, tenant_repo, demo_snapshot = _tenant_repo_patch_stack()
    with stack:
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=None))
        stack.enter_context(
            patch.object(
                tenant_repo,
                "get_snapshot_by_slug",
                side_effect=lambda slug: demo_snapshot if slug == "demo" else None,
            )
        )
        client = TestClient(app, base_url=f"http://demo.{settings.tenant_base_domain}")
        response = client.get("/api/platform-only-auth-check")

    assert response.status_code == 401


def test_platform_only_permission_engine_enforces_platform_permission():
    app = _build_platform_only_app()
    router = APIRouter()

    @router.get("/platform-only-permission-check")
    def _permission_check(
        tenant: RequiredTenantContextDep,
        current_user: User = Depends(require_permission("settings.read")),
    ):
        return {"tenant": tenant.slug, "user_id": current_user.id}

    app.include_router(router, prefix="/api")
    permission_service = PermissionService()
    permission_service.register_permissions(("settings.read",))
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        email="owner@example.com",
        password_hash="",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
    )

    stack, tenant_repo, demo_snapshot = _tenant_repo_patch_stack()
    with stack:
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=None))
        stack.enter_context(
            patch.object(
                tenant_repo,
                "get_snapshot_by_slug",
                side_effect=lambda slug: demo_snapshot if slug == "demo" else None,
            )
        )
        stack.enter_context(
            patch("core.platform.auth.auth_dependencies.get_permission_service", return_value=permission_service)
        )
        client = TestClient(app, base_url=f"http://demo.{settings.tenant_base_domain}")
        response = client.get("/api/platform-only-permission-check")

    assert response.status_code == 200
    assert response.json()["tenant"] == "demo"
    assert response.json()["user_id"] == 1
    app.dependency_overrides.pop(get_current_user, None)
