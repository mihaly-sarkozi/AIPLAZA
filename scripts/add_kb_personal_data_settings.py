#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz: knowledge_bases táblához personal_data_mode, personal_data_sensitivity
oszlopok, valamint kb_personal_data tábla létrehozása (PostgreSQL).
Új tenantoknál a create_tenant_schema már létrehozza (KbPersonalDataORM import).

Használat:
  python scripts/add_kb_personal_data_settings.py
"""
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
            # Oszlopok hozzáadása (ha még nincsenek)
            conn.execute(text(f"""
                ALTER TABLE "{safe}".knowledge_bases
                ADD COLUMN IF NOT EXISTS personal_data_mode VARCHAR(32) NOT NULL DEFAULT 'no_personal_data'
            """))
            conn.execute(text(f"""
                ALTER TABLE "{safe}".knowledge_bases
                ADD COLUMN IF NOT EXISTS personal_data_sensitivity VARCHAR(16) NOT NULL DEFAULT 'medium'
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{safe}".kb_personal_data (
                    id SERIAL PRIMARY KEY,
                    kb_id INTEGER NOT NULL REFERENCES "{safe}".knowledge_bases(id) ON DELETE CASCADE,
                    data_type VARCHAR(64) NOT NULL,
                    extracted_value TEXT NOT NULL,
                    reference_id VARCHAR(36) NOT NULL
                )
            """))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_personal_data_kb_id ON "{safe}".kb_personal_data (kb_id)'))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_personal_data_data_type ON "{safe}".kb_personal_data (data_type)'))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_personal_data_reference_id ON "{safe}".kb_personal_data (reference_id)'))
            conn.commit()
        print(f"  {safe}.knowledge_bases (+ personal_data_*), {safe}.kb_personal_data")
    print("Kész.")


if __name__ == "__main__":
    main()
