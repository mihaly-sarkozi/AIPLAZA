# backend/core/infrastructure/audit/tenant_hooks.py
# Feladat: Az audit_log tenant schema hook regisztrációját tartalmazza. Tenant schema létrehozáskor telepíti az audit_log táblát, és idempotens ALTER/INDEX statementekkel biztosítja az actor, outcome, target és correlation mezőket. Tenant provisioning adapter az audit infrastruktúrához.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from core.infrastructure.audit.models.audit_log_orm import AuditLogORM
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


# Ez a függvény telepíti a(z) audit séma logikáját.
def _install_audit_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, (AuditLogORM.__table__,))
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS actor_type VARCHAR(32) NOT NULL DEFAULT \'system\'',
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS event_name VARCHAR(128) NULL',
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS outcome VARCHAR(32) NULL',
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS target_type VARCHAR(64) NULL',
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS target_id VARCHAR(128) NULL',
            'ALTER TABLE "{schema}".audit_log ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(128) NULL',
            'CREATE INDEX IF NOT EXISTS ix_audit_log_event_name ON "{schema}".audit_log (event_name)',
            'CREATE INDEX IF NOT EXISTS ix_audit_log_outcome ON "{schema}".audit_log (outcome)',
            'CREATE INDEX IF NOT EXISTS ix_audit_log_target_type ON "{schema}".audit_log (target_type)',
            'CREATE INDEX IF NOT EXISTS ix_audit_log_target_id ON "{schema}".audit_log (target_id)',
            'CREATE INDEX IF NOT EXISTS ix_audit_log_correlation_id ON "{schema}".audit_log (correlation_id)',
        ),
    )


# Ez a függvény regisztrálja a(z) audit tenant hookok logikáját.
def register_audit_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="audit",
                install=_install_audit_schema,
                table_names=("audit_log",),
            )
        ]
    )
