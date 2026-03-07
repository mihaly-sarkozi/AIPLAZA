import os
import sys
from pathlib import Path

# Projekt gyökér a path-on (config, apps importokhoz)
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from config.settings import settings
from apps.auth.infrastructure.db.models import (
    PublicBase,
    TenantORM,
    TenantConfigORM,
    TenantDomainORM,
    TenantSchemaBase,
    SessionORM,
    SettingsORM,
    TwoFactorCodeORM,
    Pending2FAORM,
)
from apps.auth.infrastructure.db.tenant_schema import create_tenant_schema


def ensure_database_exists(url: str) -> None:
    """Ha az adatbázis nem létezik, létrehozza (PostgreSQL: postgres DB-hez csatlakozva)."""
    parsed = make_url(url)
    db_name = parsed.database
    if not db_name:
        return
    # Csatlakozás a postgres alapértelmezett DB-hez
    parsed = parsed.set(database="postgres")
    server_url = str(parsed)
    engine = create_engine(server_url, future=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name})
        if r.scalar() is None:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Adatbázis létrehozva: {db_name}")
    engine.dispose()


ensure_database_exists(settings.database_url)
engine = create_engine(settings.database_url, future=True)

# Public séma + táblák: nyers SQL DDL, hogy biztosan meglegyenek (create_all helyett)
with engine.connect() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS public.tenants (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(64) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            security_version INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """))
    conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS public.tenant_configs (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE UNIQUE,
            package VARCHAR(64) NOT NULL DEFAULT 'free',
            feature_flags JSONB NOT NULL DEFAULT '{}',
            limits JSONB NOT NULL DEFAULT '{}'
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_configs_tenant_id ON public.tenant_configs(tenant_id)"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS public.tenant_domains (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            domain VARCHAR(255) NOT NULL,
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_domains_domain ON public.tenant_domains(domain)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_domains_tenant_id ON public.tenant_domains(tenant_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_domains_domain ON public.tenant_domains(domain)"))
    conn.commit()
print("Public séma: tenants, tenant_configs, tenant_domains létrehozva/ellenőrizve.")

# Demo tenant séma + táblák (users, sessions, settings, stb.) és demo bejegyzés public.tenants-be
DEMO_SLUG = "demo"
with engine.connect() as conn:
    conn.execute(text("INSERT INTO public.tenants (slug, name, security_version, is_active) VALUES (:s, :n, 0, TRUE) ON CONFLICT (slug) DO NOTHING"), {"s": DEMO_SLUG, "n": "Demo"})
    conn.commit()
create_tenant_schema(engine, DEMO_SLUG)
print("Demo séma + táblák (users, sessions, settings, ...) létrehozva; public.tenants-ben demo bejegyzés.")

# Meglévő tenant sémák users táblájában biztosítjuk a name oszlopot (ha korábban nem volt).
with engine.connect() as conn:
    slugs = [row[0] for row in conn.execute(text("SELECT slug FROM public.tenants")).fetchall()]
    for slug in slugs:
        safe = "".join(c for c in slug if c.isalnum() or c == "_")
        if safe != slug:
            continue
        try:
            conn.execute(text(f'ALTER TABLE "{safe}".users ADD COLUMN IF NOT EXISTS name VARCHAR(255) NULL'))
            conn.execute(text(f'ALTER TABLE "{safe}".users ADD COLUMN IF NOT EXISTS registration_completed_at TIMESTAMP WITH TIME ZONE NULL'))
            conn.execute(text(f'ALTER TABLE "{safe}".users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0'))
            conn.execute(text(f'ALTER TABLE "{safe}".users ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0'))
        except Exception as e:
            if "does not exist" in str(e).lower():
                pass  # séma/users még nincs, seed_user fogja létrehozni
            else:
                raise
        try:
            conn.execute(text(f'ALTER TABLE "{safe}".two_factor_codes ADD COLUMN IF NOT EXISTS code_hash VARCHAR(64) NOT NULL DEFAULT \'\''))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_2fa_user_code_hash ON "{safe}".two_factor_codes (user_id, code_hash)'))
            conn.execute(text(f'ALTER TABLE "{safe}".two_factor_codes DROP COLUMN IF EXISTS code'))
        except Exception as e:
            if "does not exist" in str(e).lower():
                pass
            else:
                raise
    conn.commit()
print("Tenant users + two_factor_codes (code_hash, code oszlop eltávolítva) ellenőrizve.")
