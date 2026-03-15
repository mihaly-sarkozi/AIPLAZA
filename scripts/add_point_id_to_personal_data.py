#!/usr/bin/env python3
"""
Add point_id column to kb_personal_data (PostgreSQL).
A point_id összeköti a személyes adatot a tanítási napló bejegyzéssel.

Használat:
  python scripts/add_point_id_to_personal_data.py
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
            conn.execute(text(f'''
                ALTER TABLE "{safe}".kb_personal_data
                ADD COLUMN IF NOT EXISTS point_id VARCHAR(36) NULL
            '''))
            conn.execute(text(f'''
                CREATE INDEX IF NOT EXISTS ix_kb_personal_data_point_id
                ON "{safe}".kb_personal_data (point_id)
            '''))
            conn.commit()
        print(f"  {safe}.kb_personal_data: point_id")
    print("Kész.")


if __name__ == "__main__":
    main()
