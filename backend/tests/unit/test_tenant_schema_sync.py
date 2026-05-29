from sqlalchemy import Column, Integer, MetaData, Table

from apps.knowledge.bootstrap.tenant_hooks import register_knowledge_tenant_hooks
import core.modules.tenant.schema.hooks as tenant_schema_hooks
from core.modules.tenant.service import tenant_schema_service


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _stmt):
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return _FakeConn(self._rows)


def test_sync_existing_tenant_schemas_reconciles_valid_slugs(monkeypatch):
    engine = _FakeEngine([("demo",), ("acme-1",), ("bad slug",)])
    created = []
    public_upgrades = []

    def _fake_create_tenant_schema(_engine, slug):
        created.append((_engine, slug))

    def _fake_upgrade_public_schema(_engine):
        public_upgrades.append(_engine)

    monkeypatch.setattr(tenant_schema_service, "upgrade_tenant_schema", _fake_create_tenant_schema)
    monkeypatch.setattr(tenant_schema_service, "upgrade_public_schema", _fake_upgrade_public_schema)

    tenant_schema_service.sync_existing_tenant_schemas(engine)

    assert public_upgrades == [engine]
    assert created == [(engine, "demo"), (engine, "acme-1")]


def test_list_tenant_schema_table_names_uses_registered_hooks(monkeypatch):
    metadata = MetaData()
    Table("users", metadata, Column("id", Integer, primary_key=True))
    Table("settings", metadata, Column("id", Integer, primary_key=True))

    monkeypatch.setattr(tenant_schema_hooks, "_registered_hooks", {})
    monkeypatch.setattr(tenant_schema_hooks, "_kernel_hooks", ())
    tenant_schema_service.register_tenant_schema_hooks(
        [
            tenant_schema_service.TenantSchemaHook(
                name="users",
                install=lambda engine, slug: None,
                table_names=("users",),
            ),
            tenant_schema_service.TenantSchemaHook(
                name="settings",
                install=lambda engine, slug: None,
                table_names=("settings",),
            ),
        ]
    )

    assert tenant_schema_service.list_tenant_schema_table_names() == ["settings", "users"]


def test_knowledge_fk_constraints_revision_runs_after_base_schema(monkeypatch):
    monkeypatch.setattr(tenant_schema_hooks, "_registered_hooks", {})
    monkeypatch.setattr(tenant_schema_hooks, "_kernel_hooks", ())

    register_knowledge_tenant_hooks()

    revisions = [
        tenant_schema_service.tenant_migration_revision(hook)
        for hook in tenant_schema_service.list_tenant_schema_hooks()
        if hook.name.startswith("knowledge")
    ]
    assert "knowledge.schema.worker_first_ingest.v6.kb_visibility_flags" in revisions
    assert "knowledge.schema.worker_first_ingest.v5.referential_integrity" in revisions
    assert revisions.index("knowledge.schema.worker_first_ingest.v5.referential_integrity") < revisions.index(
        "knowledge.schema.worker_first_ingest.v6.kb_visibility_flags"
    )
