#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz hozzáadja a kb_training_log táblát (PostgreSQL).
Új tenantoknál a create_tenant_schema már létrehozza (KbTrainingLogORM import).

Használat:
  python scripts/add_kb_training_log_table.py
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
                CREATE TABLE IF NOT EXISTS "{safe}".kb_training_log (
                    id SERIAL PRIMARY KEY,
                    kb_id INTEGER NOT NULL REFERENCES "{safe}".knowledge_bases(id) ON DELETE CASCADE,
                    point_id VARCHAR(36) NOT NULL,
                    user_id INTEGER NULL REFERENCES "{safe}".users(id) ON DELETE SET NULL,
                    user_display VARCHAR(255) NULL,
                    title VARCHAR(512) NOT NULL,
                    content TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_training_log_kb_id ON "{safe}".kb_training_log (kb_id)'))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_training_log_point_id ON "{safe}".kb_training_log (point_id)'))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_kb_training_log_created_at ON "{safe}".kb_training_log (created_at)'))
            conn.commit()
        print(f"  {safe}.kb_training_log")
    print("Kész.")


if __name__ == "__main__":
    main()
