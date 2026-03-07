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
    TenantSchemaBase,
    SessionORM,
    SettingsORM,
    TwoFactorCodeORM,
    Pending2FAORM,
)


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
# Csak public.tenants – a tenant-specifikus táblák (users, sessions, stb., name oszloppal) tenantonként
# külön sémában a seed_user vagy create_tenant_schema hozza létre (TenantSchemaBase / UserORM alapján).
PublicBase.metadata.create_all(engine)
print("Public séma: tenants tábla létrehozva. Tenant sémákat a seed_user vagy API hozza létre.")

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
        except Exception as e:
            if "does not exist" in str(e).lower():
                pass  # séma/users még nincs, seed_user fogja létrehozni
            else:
                raise
    conn.commit()
print("Tenant users táblák: name, registration_completed_at, failed_login_attempts oszlopok ellenőrizve (ADD COLUMN IF NOT EXISTS).")
