from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.modules.tenant.dto import TenantConfig, TenantDomain, TenantDomainInfo, TenantSnapshot, TenantStatus
from core.modules.tenant.domain.tenant_policy import DomainRoutingPolicy, TenantLifecyclePolicy


def _snapshot(*, is_active: bool, suspended_reason: str | None = None) -> TenantSnapshot:
    return TenantSnapshot(
        tenant_id=7,
        slug="acme",
        name="Acme",
        created_at=datetime.now(timezone.utc),
        security_version=0,
        status=TenantStatus(
            tenant_id=7,
            slug="acme",
            is_active=is_active,
            suspended_reason=suspended_reason,
        ),
        config=TenantConfig(tenant_id=7, slug="acme", package="free", feature_flags={}, limits={}),
        domain=TenantDomainInfo(
            request_host="acme.app.test",
            resolved_host="acme.app.test",
            is_custom_domain=False,
            verified_at=None,
        ),
    )


def test_tenant_lifecycle_policy_allows_provisioning_to_active_transition():
    policy = TenantLifecyclePolicy()

    policy.assert_transition(
        TenantStatus(tenant_id=7, slug="acme", is_active=False, suspended_reason=None),
        TenantLifecyclePolicy.ACTIVE,
    )


def test_tenant_lifecycle_policy_blocks_routing_for_suspended_tenant():
    policy = TenantLifecyclePolicy()

    with pytest.raises(ValueError, match="tenant_not_routable:suspended"):
        policy.assert_routable(_snapshot(is_active=False, suspended_reason="payment_overdue"))


def test_domain_routing_policy_classifies_custom_domain_states():
    policy = DomainRoutingPolicy(tenant_base_domain="app.test")

    pending = policy.classify_domain_record(
        TenantDomain(id=1, tenant_id=7, domain="portal.acme.test", verified_at=None),
        tenant_slug="acme",
    )
    verified = policy.classify_domain_record(
        TenantDomain(id=2, tenant_id=7, domain="portal.acme.test", verified_at=datetime.now(timezone.utc)),
        tenant_slug="acme",
    )

    assert pending == "custom_pending"
    assert verified == "custom_verified"
