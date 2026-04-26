from __future__ import annotations

from core.extensions.tenant.service import TenantSchemaHook, register_tenant_schema_hooks, run_schema_statements


def _install_profile_schema(engine, slug: str) -> None:
    run_schema_statements(
        engine,
        slug,
        (
            """
            CREATE TABLE IF NOT EXISTS "{schema}".profile_preferences (
                user_id INTEGER PRIMARY KEY,
                dashboard_layout VARCHAR(32) NOT NULL DEFAULT 'comfortable',
                show_tips BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """,
        ),
    )


def register_profile_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="profile",
                install=_install_profile_schema,
                table_names=("profile_preferences",),
            )
        ]
    )


__all__ = ["register_profile_tenant_hooks"]
