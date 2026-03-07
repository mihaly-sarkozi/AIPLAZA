#!/usr/bin/env python3
"""
Csak a tenant sémát + táblákat hozza létre (users, sessions, settings, two_factor_codes, pending_2fa_logins).
A tenant sornak már léteznie kell a public.tenants-ben (pl. seed_user vagy manuális INSERT).

Használat:
  python scripts/create_tenant_schema.py              # demo (alap)
  TENANT_SLUG=acme python scripts/create_tenant_schema.py
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine
from config.settings import settings
from apps.auth.infrastructure.db.tenant_schema import create_tenant_schema


def main():
    slug = os.getenv("TENANT_SLUG", "demo")
    engine = create_engine(settings.database_url, future=True)
    create_tenant_schema(engine, slug)
    print(f"Tenant séma + táblák létrehozva: {slug}")


if __name__ == "__main__":
    main()
