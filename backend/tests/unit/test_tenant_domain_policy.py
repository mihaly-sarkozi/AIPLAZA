from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.modules.tenant.repositories.tenant_repository import TenantRepository
from core.modules.tenant.service.tenant_domain_verification_service import (
    TenantDomainVerificationService,
)


class _FakeQuery:
    def __init__(self, result):
        self._result = result
        self.filter_args = None

    def filter(self, *args):
        self.filter_args = args
        return self

    def first(self):
        return self._result


class _FakeDb:
    def __init__(self, link=None, tenant=None):
        self.link_query = _FakeQuery(link)
        self.tenant = tenant
        self.committed = False
        self.refreshed = None

    def execute(self, _stmt):
        return None

    def query(self, _model):
        return self.link_query

    def get(self, _model, _tenant_id):
        return self.tenant

    def commit(self):
        self.committed = True

    def refresh(self, row):
        self.refreshed = row


class _FakeSessionFactory:
    def __init__(self, db):
        self._db = db

    def __call__(self):
        return self

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_by_domain_requires_verified_domain():
    tenant_row = SimpleNamespace(
        id=7,
        slug="acme",
        name="Acme",
        created_at=datetime.now(timezone.utc),
        security_version=0,
    )
    db = _FakeDb(link=SimpleNamespace(tenant_id=7), tenant=tenant_row)
    repo = TenantRepository(_FakeSessionFactory(db))

    tenant = repo.get_by_domain(" Portal.Acme.Test ")

    assert tenant is not None
    assert tenant.slug == "acme"
    assert db.link_query.filter_args is not None
    assert len(db.link_query.filter_args) == 2


def test_verify_domain_sets_timestamp_and_invalidates_cache():
    tenant_repo = MagicMock()
    tenant_repo.verify_domain.return_value = SimpleNamespace(domain="portal.acme.test")
    service = TenantDomainVerificationService(tenant_repo)
    service._assert_dns_challenge = MagicMock()  # type: ignore[method-assign]
    service._assert_dns_points_to_platform = MagicMock()  # type: ignore[method-assign]

    result = service.verify_domain("Portal.Acme.Test", tenant_id=7, actor_user_id=42)

    assert result is not None
    tenant_repo.verify_domain.assert_called_once()
    args, kwargs = tenant_repo.verify_domain.call_args
    assert args[0] == "portal.acme.test"
    assert kwargs["updated_by"] == 42
    assert kwargs["verified_at"] is not None
