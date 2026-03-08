#!/usr/bin/env python3
"""
Első user (owner) rögzítése: tenant (public.tenants) + tenant séma (pl. demo) + egy user role=owner.
A tenant sémában lévő táblák tartalma törlődik (TRUNCATE CASCADE), majd létrejön az első user.
Ez az első rögzítés – üres tenantnél a seed_user adja az ownert; később meghívásos regisztrációval
az első set-passwordöt befejező is owner lehet (ha még nincs owner).
Futtatás: python scripts/seed_user.py
Környezeti változók (opcionális):
  TENANT_SLUG (pl. demo) – tenant slug = séma név, alap: demo
  TENANT_NAME – megjelenített név, alap: Demo Cég
  ADMIN_EMAIL, ADMIN_PASSWORD – első user (owner) belépési adatai
  ADMIN_NAME – megjelenített név (opcionális)
  ADMIN_ROLE – alap: owner (első user). user|admin is megadható.
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt_sha256 as pwd_hasher

from config.settings import settings
from apps.auth.infrastructure.db.models import PublicBase, TenantORM, TenantSchemaBase
from apps.users.infrastructure.db.models import UserORM
from apps.auth.infrastructure.db.tenant_schema import create_tenant_schema


def main():
    tenant_slug = os.getenv("TENANT_SLUG", "demo")
    tenant_name = os.getenv("TENANT_NAME", "Demo Cég")
    email = os.getenv("ADMIN_EMAIL", "sarkozi.mihaly@gmail.com")
    password = os.getenv("ADMIN_PASSWORD", "123")
    admin_name = os.getenv("ADMIN_NAME", "Sárközi Mihály") # opcionális
    # Első user a tenantben = owner (jogosultságkezelés + később fizetés)
    role = os.getenv("ADMIN_ROLE", "owner")

    engine = create_engine(settings.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    pwd_hash = pwd_hasher.hash(password)

    with SessionLocal() as s:
        # public.tenants: tenant sor
        s.execute(text("SET search_path TO public"))
        tenant = s.query(TenantORM).filter(TenantORM.slug == tenant_slug).first()
        if not tenant:
            tenant = TenantORM(slug=tenant_slug, name=tenant_name)
            s.add(tenant)
            s.commit()
            s.refresh(tenant)
            print("Tenant létrehozva (public.tenants):", tenant_slug, "|", tenant_name)
        else:
            print("Tenant már létezik:", tenant_slug)

    # Tenant séma + táblák (users, sessions, ...) – script kontextusban nincs contextvar
    create_tenant_schema(engine, tenant_slug)

    safe_slug = "".join(c for c in tenant_slug if c.isalnum() or c in "_-")
    if safe_slug != tenant_slug:
        print("Érvénytelen TENANT_SLUG:", tenant_slug)
        return

    # Tenant séma tábláinak tartalmának törlése (TRUNCATE CASCADE)
    table_names = [t.name for t in TenantSchemaBase.metadata.sorted_tables]
    if table_names:
        tables_sql = ", ".join(f'"{safe_slug}"."{t}"' for t in table_names)
        with engine.connect() as conn:
            conn.execute(text(f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE"))
            conn.commit()
        print("Tenant táblák tartalma törölve:", safe_slug)

    # Régi séma: is_superuser oszlop törlése, ha még megvan (migráció owner-re)
    with engine.connect() as conn:
        r = conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :s AND table_name = 'users' AND column_name = 'is_superuser'
            """),
            {"s": safe_slug},
        )
        if r.scalar() is not None:
            conn.execute(text(f'ALTER TABLE "{safe_slug}".users DROP COLUMN IF EXISTS is_superuser'))
            conn.commit()
            print("  is_superuser oszlop törölve (régi séma).")

    with SessionLocal() as s:
        # User a tenant sémában (pl. demo.users)
        s.execute(text(f'SET search_path TO "{safe_slug}"'))
        u = UserORM(
            email=email,
            name=admin_name,
            password_hash=pwd_hash,
            is_active=True,
            role=role,
        )
        s.add(u)
        s.commit()
        print("User létrehozva:", email, "| tenant:", tenant_slug, "| role:", role)
        print("Belépés: http://" + tenant_slug + ".local:8001 (vagy a beállított host)")
        print("Jelszó (csak dev!):", password)


if __name__ == "__main__":
    main()
