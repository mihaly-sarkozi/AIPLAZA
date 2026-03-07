#!/usr/bin/env python3
"""
Users táblához name oszlop hozzáadása (tenant sémákban).
Futtatás: python scripts/add_user_name_column.py
Környezet: TENANT_SLUG opcionális (pl. demo); ha nincs, minden tenant sémát frissít.
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
    slug = os.getenv("TENANT_SLUG")
    if slug:
        slugs = [slug]
    else:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT slug FROM public.tenants"))
            slugs = [row[0] for row in r]
    for s in slugs:
        safe = "".join(c for c in s if c.isalnum() or c == "_")
        if safe != s:
            continue
        with engine.connect() as conn:
            conn.execute(text(f'ALTER TABLE "{safe}".users ADD COLUMN IF NOT EXISTS name VARCHAR(255) NULL'))
            conn.commit()
        print(f"OK: {safe}.users.name")
    print("Kész.")


if __name__ == "__main__":
    main()
