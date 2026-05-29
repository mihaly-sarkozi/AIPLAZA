# backend/core/modules/users/tenant_hooks.py
# Feladat: A users tenant schema hook regisztrációját tartalmazza. Tenant schema létrehozáskor telepíti a users és user_invite_tokens táblákat, valamint idempotens ALTER statementekkel biztosítja a profil, auth és lifecycle mezőket. Tenant provisioning adapter a users perzisztenciához.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.modules.users.models.user_invite_token_orm import UserInviteTokenORM
from core.modules.users.models.user_orm import UserORM


# Ez a függvény telepíti a(z) felhasználók séma logikáját.
def _install_users_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, (UserORM.__table__, UserInviteTokenORM.__table__))
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE NULL',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS deleted_by INTEGER NULL',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS registration_completed_at TIMESTAMP WITH TIME ZONE NULL',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS credentials_password_set BOOLEAN NOT NULL DEFAULT TRUE',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS pending_email VARCHAR(255) NULL',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS pending_email_token_hash VARCHAR(255) NULL',
            'ALTER TABLE "{schema}".users ADD COLUMN IF NOT EXISTS pending_email_expires_at TIMESTAMP WITH TIME ZONE NULL',
            'CREATE INDEX IF NOT EXISTS ix_users_pending_email_token_hash ON "{schema}".users (pending_email_token_hash)',
            'ALTER TABLE "{schema}".user_invite_tokens ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".user_invite_tokens ADD COLUMN IF NOT EXISTS created_by INTEGER NULL',
            'ALTER TABLE "{schema}".user_invite_tokens ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".user_invite_tokens ADD COLUMN IF NOT EXISTS updated_by INTEGER NULL',
        ),
    )


# Ez a függvény regisztrálja a(z) felhasználók tenant hookok logikáját.
def register_users_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="users",
                # Uj migration revision: meglevo tenantokon ujra lefut az install (ADD COLUMN IF NOT EXISTS).
                revision="users_pending_email_change",
                install=_install_users_schema,
                table_names=("users", "user_invite_tokens"),
            )
        ]
    )
