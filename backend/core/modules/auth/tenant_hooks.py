# backend/core/modules/auth/tenant_hooks.py
# Feladat: Az auth modul tenant schema telepítési hookját regisztrálja. Létrehozza és kompatibilisen frissíti a refresh token, 2FA code, 2FA attempt, pending 2FA és user authenticator táblákat minden tenant sémában. Auth tenant provisioning adapter, amelyet az AuthCoreModule tenant_schema_hooks metódusa köt be.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.auth.models.pending_2fa_orm import Pending2FAORM
from core.modules.auth.models.session_orm import SessionORM
from core.modules.auth.models.two_factor_attempt_orm import TwoFactorAttemptORM
from core.modules.auth.models.two_factor_code_orm import TwoFactorCodeORM
from core.modules.auth.models.user_authenticator_orm import UserAuthenticatorORM
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


# Ez a függvény telepíti a(z) auth séma logikáját.
def _install_auth_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            SessionORM.__table__,
            TwoFactorCodeORM.__table__,
            TwoFactorAttemptORM.__table__,
            Pending2FAORM.__table__,
            UserAuthenticatorORM.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".refresh_tokens ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".refresh_tokens ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".refresh_tokens ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".two_factor_codes ADD COLUMN IF NOT EXISTS code_hash VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".two_factor_codes ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".two_factor_codes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".two_factor_codes ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'CREATE INDEX IF NOT EXISTS ix_2fa_user_code_hash ON "{schema}".two_factor_codes (user_id, code_hash)',
            'ALTER TABLE "{schema}".two_factor_codes DROP COLUMN IF EXISTS code',
            'ALTER TABLE "{schema}".two_factor_attempts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".two_factor_attempts ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".two_factor_attempts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".two_factor_attempts ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".pending_2fa_logins ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".user_authenticators ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".user_authenticators ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".user_authenticators ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".user_authenticators ADD COLUMN IF NOT EXISTS pending_secret_base32 VARCHAR(128)',
            'ALTER TABLE "{schema}".user_authenticators ADD COLUMN IF NOT EXISTS pending_expires_at TIMESTAMP WITH TIME ZONE',
        ),
    )


# Ez a függvény regisztrálja a(z) auth tenant hookok logikáját.
def register_auth_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="auth",
                install=_install_auth_schema,
                table_names=(
                    "refresh_tokens",
                    "two_factor_codes",
                    "two_factor_attempts",
                    "pending_2fa_logins",
                    "user_authenticators",
                ),
            )
        ]
    )
