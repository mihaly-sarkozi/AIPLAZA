# apps/auth/infrastructure/db/tenant_schema.py
# Új tenant séma + táblák (users, sessions, ...) létrehozása. A public.tenants kívül minden tenant saját sémában van.
# 2026.02.14 - Sárközi Mihály

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Engine

from apps.auth.infrastructure.db.models import TenantSchemaBase
from apps.users.infrastructure.db.models import UserORM, UserInviteTokenORM  # noqa: F401 – users, user_invite_tokens
from apps.audit.infrastructure.db.models import AuditLogORM  # noqa: F401 – audit_log tábla
from apps.knowledge.infrastructure.db.models import KBORM, KbUserPermissionORM  # noqa: F401 – knowledge_bases, kb_user_permission


def create_tenant_schema(engine: Engine, slug: str) -> None:
    """Létrehozza a tenant sémát és benne az összes táblát (users, sessions, settings, two_factor_codes, pending_2fa_logins)."""
    # Slug: betű, szám, aláhúzás, kötőjel (pl. ferike-hu). PostgreSQL idézett azonosítóban megengedett.
    safe_slug = "".join(c for c in slug if c.isalnum() or c in "_-")
    if safe_slug != slug:
        raise ValueError(f"Érvénytelen tenant slug: {slug!r}")

    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{safe_slug}"'))
        conn.commit()

    # create_all(schemas=[...]) nem minden SQLAlchemy verzióban van; táblákat másoljuk a sémával
    temp_metadata = MetaData()
    for table in TenantSchemaBase.metadata.sorted_tables:
        table.to_metadata(temp_metadata, schema=safe_slug)
    temp_metadata.create_all(engine)
