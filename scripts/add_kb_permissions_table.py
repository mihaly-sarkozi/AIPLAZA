#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz hozzáadja a kb_user_permission táblát.
Új tenantoknál a create_tenant_schema már létrehozza (KbUserPermissionORM import).

Használat:
  python scripts/add_kb_permissions_table.py
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine, text
from config.settings import settings


def main():
    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r[0]]
    if not slugs:
        print("Nincs tenant séma (public.tenants üres).")
        return
    for slug in slugs:
        safe = "".join(c for c in slug if c.isalnum() or c in "_-")
        if safe != slug:
            print(f"Kihagyva (érvénytelen slug): {slug}")
            continue
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{safe}".kb_user_permission (
                    id SERIAL PRIMARY KEY,
                    kb_id INTEGER NOT NULL REFERENCES "{safe}".knowledge_bases(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES "{safe}".users(id) ON DELETE CASCADE,
                    permission VARCHAR(10) NOT NULL,
                    CONSTRAINT uq_kb_user_permission_kb_user UNIQUE (kb_id, user_id)
                )
            """))
            conn.commit()
        print(f"  {safe}.kb_user_permission")
    print("Kész.")


if __name__ == "__main__":
    main()
