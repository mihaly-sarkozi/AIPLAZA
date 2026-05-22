from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.modules.tenant.dto import TenantConfig, TenantSnapshot, TenantStatus
from core.modules.tenant.domain.tenant_policy import TenantLifecyclePolicy
from core.modules.tenant.service.tenant_provisioning_service import (
    TenantProvisioningRequest,
    TenantProvisioningService,
)


def _snapshot(slug: str) -> TenantSnapshot:
    return TenantSnapshot(
        tenant_id=1,
        slug=slug,
        name="Acme",
        created_at=datetime.now(timezone.utc),
        security_version=0,
        status=TenantStatus(tenant_id=1, slug=slug, is_active=True),
        config=TenantConfig(tenant_id=1, slug=slug, package="free", feature_flags={}, limits={}),
        domain=None,
    )


def test_provision_rolls_back_schema_and_public_tenant_on_owner_failure():
    tenant_repo = MagicMock()
    tenant_repo.create.return_value = SimpleNamespace(id=11, slug="acme")
    tenant_repo.get_by_slug.side_effect = [None, SimpleNamespace(id=11, slug="acme"), None]
    tenant_repo.get_actor_user_id.return_value = None
    tenant_repo.get_config_by_tenant_id.return_value = None
    tenant_repo.get_domain.return_value = None
    user_service = MagicMock()
    user_service.create.side_effect = RuntimeError("owner create failed")
    user_service.user_repository.get_by_email.return_value = None
    schema_manager = MagicMock()
    schema_manager.exists.side_effect = [False, True]

    svc = TenantProvisioningService(
        tenant_repository=tenant_repo,
        user_service=user_service,
        schema_manager=schema_manager,
        request_base_url_builder=lambda slug: f"https://{slug}.example.com",
        lifecycle_policy=TenantLifecyclePolicy(),
    )

    req = TenantProvisioningRequest(
        slug="acme",
        tenant_name="Acme",
        owner_email="owner@acme.test",
        owner_name="Owner",
        primary_domain="acme.example.com",
    )

    with pytest.raises(RuntimeError, match="owner create failed"):
        svc.provision(req)

    schema_manager.create.assert_called_once_with("acme")
    schema_manager.drop.assert_called_once_with("acme")
    tenant_repo.delete_by_slug.assert_called_once_with("acme")


def test_provision_builds_initial_tenant_state():
    tenant_repo = MagicMock()
    tenant_repo.create.return_value = SimpleNamespace(id=7, slug="acme")
    tenant = SimpleNamespace(id=7, slug="acme")
    tenant_repo.get_by_slug.side_effect = [None, tenant]
    tenant_repo.get_actor_user_id.return_value = None
    tenant_repo.get_config_by_tenant_id.side_effect = [
        None,
        TenantConfig(tenant_id=7, slug="acme", package="free", feature_flags={}, limits={}),
    ]
    tenant_repo.get_domain.side_effect = [
        None,
        SimpleNamespace(tenant_id=7, domain="acme.example.com"),
        None,
    ]
    tenant_repo.get_tenant_status.return_value = TenantStatus(tenant_id=7, slug="acme", is_active=False)
    tenant_repo.get_snapshot_by_slug.return_value = _snapshot("acme")
    user_service = MagicMock()
    user_service.create.return_value = SimpleNamespace(id=99)
    user_service.user_repository.get_by_email.side_effect = [None, SimpleNamespace(id=99, role="owner")]
    schema_manager = MagicMock()
    schema_manager.exists.return_value = True
    schema_manager.list_missing_tables.return_value = ()

    svc = TenantProvisioningService(
        tenant_repository=tenant_repo,
        user_service=user_service,
        schema_manager=schema_manager,
        request_base_url_builder=lambda slug: f"https://{slug}.example.com",
        lifecycle_policy=TenantLifecyclePolicy(),
    )

    req = TenantProvisioningRequest(
        slug="acme",
        tenant_name="Acme",
        owner_email="owner@acme.test",
        owner_name="Owner",
        primary_domain="acme.example.com",
    )

    result = svc.provision(req)

    tenant_repo.create.assert_called_once_with("acme", "Acme", created_by=None, is_active=False)
    tenant_repo.set_actor.assert_called_once_with(7, 99, updated_by=99)
    tenant_repo.create_config.assert_called_once()
    tenant_repo.create_domain.assert_called_once_with(7, "acme.example.com", created_by=99)
    tenant_repo.activate.assert_called_once_with(7, updated_by=99)
    assert result.slug == "acme"
    assert result.domain is not None
    assert result.domain.resolved_host == "acme.example.com"
    assert result.domain.verified_at is None


def test_provision_creates_custom_domain_without_auto_verify():
    tenant_repo = MagicMock()
    tenant_repo.create.return_value = SimpleNamespace(id=7, slug="acme")
    tenant = SimpleNamespace(id=7, slug="acme")
    tenant_repo.get_by_slug.side_effect = [None, tenant]
    tenant_repo.get_actor_user_id.return_value = None
    tenant_repo.get_config_by_tenant_id.side_effect = [
        None,
        TenantConfig(tenant_id=7, slug="acme", package="free", feature_flags={}, limits={}),
    ]
    tenant_repo.get_domain.side_effect = [
        None,
        None,
        SimpleNamespace(tenant_id=7, domain="acme.example.com"),
        SimpleNamespace(tenant_id=7, domain="portal.acme.test"),
    ]
    tenant_repo.get_tenant_status.return_value = TenantStatus(tenant_id=7, slug="acme", is_active=False)
    tenant_repo.get_snapshot_by_slug.return_value = _snapshot("acme")
    user_service = MagicMock()
    user_service.create.return_value = SimpleNamespace(id=99)
    user_service.user_repository.get_by_email.side_effect = [None, SimpleNamespace(id=99, role="owner")]
    schema_manager = MagicMock()
    schema_manager.exists.return_value = True
    schema_manager.list_missing_tables.return_value = ()

    svc = TenantProvisioningService(
        tenant_repository=tenant_repo,
        user_service=user_service,
        schema_manager=schema_manager,
        request_base_url_builder=lambda slug: f"https://{slug}.example.com",
        lifecycle_policy=TenantLifecyclePolicy(),
    )

    req = TenantProvisioningRequest(
        slug="acme",
        tenant_name="Acme",
        owner_email="owner@acme.test",
        owner_name="Owner",
        primary_domain="acme.example.com",
        custom_domain="portal.acme.test",
    )

    svc.provision(req)

    assert tenant_repo.create_domain.call_count == 2
    tenant_repo.create_domain.assert_any_call(7, "acme.example.com", created_by=99)
    tenant_repo.create_domain.assert_any_call(7, "portal.acme.test", created_by=99)


def test_provision_is_idempotent_when_resources_already_exist():
    tenant_repo = MagicMock()
    tenant = SimpleNamespace(id=7, slug="acme")
    tenant_repo.get_by_slug.return_value = tenant
    tenant_repo.get_actor_user_id.return_value = 99
    tenant_repo.get_config_by_tenant_id.return_value = TenantConfig(
        tenant_id=7,
        slug="acme",
        package="free",
        feature_flags={},
        limits={},
    )
    tenant_repo.get_domain.side_effect = [
        SimpleNamespace(tenant_id=7, domain="acme.example.com"),
        SimpleNamespace(tenant_id=7, domain="portal.acme.test"),
        SimpleNamespace(tenant_id=7, domain="acme.example.com"),
        SimpleNamespace(tenant_id=7, domain="portal.acme.test"),
    ]
    tenant_repo.get_tenant_status.return_value = TenantStatus(tenant_id=7, slug="acme", is_active=True)
    tenant_repo.get_snapshot_by_slug.return_value = _snapshot("acme")
    user_service = MagicMock()
    user_service.user_repository.get_by_email.side_effect = [
        SimpleNamespace(id=99, role="owner"),
        SimpleNamespace(id=99, role="owner"),
    ]
    schema_manager = MagicMock()
    schema_manager.exists.return_value = True
    schema_manager.list_missing_tables.return_value = ()

    svc = TenantProvisioningService(
        tenant_repository=tenant_repo,
        user_service=user_service,
        schema_manager=schema_manager,
        request_base_url_builder=lambda slug: f"https://{slug}.example.com",
        lifecycle_policy=TenantLifecyclePolicy(),
    )

    req = TenantProvisioningRequest(
        slug="acme",
        tenant_name="Acme",
        owner_email="owner@acme.test",
        owner_name="Owner",
        primary_domain="acme.example.com",
        custom_domain="portal.acme.test",
    )

    result = svc.provision(req)

    assert result.slug == "acme"
    tenant_repo.create.assert_not_called()
    user_service.create.assert_not_called()
    tenant_repo.set_actor.assert_not_called()
    tenant_repo.activate.assert_not_called()
    tenant_repo.create_domain.assert_not_called()
