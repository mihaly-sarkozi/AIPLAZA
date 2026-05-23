from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core.modules.tenant.repositories.tenant_repository import TenantRepository


class _FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first_result = first_result
        self._all_result = all_result or []

    def filter(self, *_args):
        return self

    def first(self):
        return self._first_result

    def all(self):
        return self._all_result


class _FakeDb:
    def __init__(self, *, tenant_row=None, config_row=None, domain_row=None, domain_rows=None):
        self.tenant_row = tenant_row
        self.config_row = config_row
        self.domain_row = domain_row
        self.domain_rows = domain_rows or []
        self.added = []
        self.deleted = []
        self.committed = False
        self.refreshed = None

    def execute(self, _stmt):
        return None

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == "TenantORM":
            return _FakeQuery(first_result=self.tenant_row)
        if model_name == "TenantConfigORM":
            return _FakeQuery(first_result=self.config_row)
        if model_name == "TenantDomainORM":
            return _FakeQuery(first_result=self.domain_row, all_result=self.domain_rows)
        raise AssertionError(f"Unexpected model queried: {model_name}")

    def get(self, model, _id):
        model_name = getattr(model, "__name__", "")
        if model_name == "TenantORM":
            return self.tenant_row
        raise AssertionError(f"Unexpected model get: {model_name}")

    def add(self, row):
        self.added.append(row)

    def delete(self, row):
        self.deleted.append(row)

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


def _tenant_row(slug: str = "acme"):
    return SimpleNamespace(
        id=7,
        slug=slug,
        name="Acme",
        created_at=datetime.now(timezone.utc),
        security_version=0,
        is_active=False,
        created_by=None,
        updated_by=None,
    )


def _domain_row(domain: str = "portal.acme.test", tenant_id: int = 7, verified_at=None):
    return SimpleNamespace(
        id=3,
        tenant_id=tenant_id,
        domain=domain,
        verified_at=verified_at,
        created_at=datetime.now(timezone.utc),
        updated_by=None,
    )


def test_activate_invalidates_tenant_snapshot_cache():
    db = _FakeDb(tenant_row=_tenant_row())
    repo = TenantRepository(_FakeSessionFactory(db))

    with patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_tenant_cache") as invalidate_tenant:
        repo.activate(7, updated_by=99)

    invalidate_tenant.assert_called_once_with("acme")


def test_increment_security_version_invalidates_tenant_snapshot_cache():
    db = _FakeDb(tenant_row=_tenant_row())
    repo = TenantRepository(_FakeSessionFactory(db))

    with patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_tenant_cache") as invalidate_tenant:
        repo.increment_security_version(7, updated_by=99)

    invalidate_tenant.assert_called_once_with("acme")


def test_create_config_invalidates_tenant_snapshot_cache():
    db = _FakeDb(tenant_row=_tenant_row(), config_row=None)
    repo = TenantRepository(_FakeSessionFactory(db))

    with patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_tenant_cache") as invalidate_tenant:
        repo.create_config(
            7,
            slug="acme",
            package="pro",
            feature_flags={"kb": True},
            limits={"users": 10},
            created_by=99,
        )

    invalidate_tenant.assert_called_once_with("acme")


def test_create_domain_invalidates_domain_cache():
    db = _FakeDb(domain_row=None)
    repo = TenantRepository(_FakeSessionFactory(db))

    with patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_domain2tenant_cache") as invalidate_domain:
        repo.create_domain(7, "Portal.Acme.Test", created_by=99)

    invalidate_domain.assert_called_once_with("portal.acme.test")


def test_verify_domain_invalidates_domain_cache():
    db = _FakeDb(domain_row=_domain_row())
    repo = TenantRepository(_FakeSessionFactory(db))

    with patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_domain2tenant_cache") as invalidate_domain:
        repo.verify_domain("Portal.Acme.Test", verified_at=datetime.now(timezone.utc), updated_by=99)

    invalidate_domain.assert_called_once_with("portal.acme.test")


def test_delete_by_slug_invalidates_tenant_and_domain_caches():
    db = _FakeDb(
        tenant_row=_tenant_row(),
        domain_rows=[_domain_row("portal.acme.test"), _domain_row("app.acme.test")],
    )
    repo = TenantRepository(_FakeSessionFactory(db))

    with (
        patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_tenant_cache") as invalidate_tenant,
        patch("core.modules.tenant.repositories.tenant_write_repository.invalidate_domain2tenant_cache") as invalidate_domain,
    ):
        repo.delete_by_slug("acme")

    invalidate_tenant.assert_called_once_with("acme")
    assert invalidate_domain.call_count == 2
    invalidate_domain.assert_any_call("portal.acme.test")
    invalidate_domain.assert_any_call("app.acme.test")
