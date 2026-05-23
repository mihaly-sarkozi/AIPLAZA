from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import Request

from core.modules.tenant.dto import TenantConfig, TenantDomainInfo, TenantSnapshot, TenantStatus
from core.kernel.deps.facade import get_tenant_context


def test_get_tenant_context_uses_snapshot_as_single_source():
    snapshot = TenantSnapshot(
        tenant_id=3,
        slug="acme",
        name="Acme",
        created_at=datetime.now(timezone.utc),
        security_version=5,
        status=TenantStatus(tenant_id=3, slug="acme", is_active=True),
        config=TenantConfig(tenant_id=3, slug="acme", package="free", feature_flags={"kb": True}, limits={"max_users": 10}),
        domain=TenantDomainInfo(
            request_host="acme.example.com",
            resolved_host="acme.example.com",
            is_custom_domain=False,
            verified_at=None,
        ),
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "state": {
                "tenant_snapshot": snapshot,
                "tenant_slug": "other",
                "tenant_security_version": 0,
                "correlation_id": "corr-1",
            },
        }
    )

    ctx = get_tenant_context(request)

    assert ctx.tenant_id == 3
    assert ctx.slug == "acme"
    assert ctx.name == "Acme"
    assert ctx.security_version == 5
    assert ctx.status == snapshot.status
    assert ctx.config == snapshot.config
    assert ctx.domain == snapshot.domain
    assert ctx.correlation_id == "corr-1"
