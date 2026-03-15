#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz kb_vector_outbox tábla létrehozása.

Használat:
  python scripts/add_kb_vector_outbox_table.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
load_dotenv(_project_root / ".env")

from config.settings import settings  # noqa: E402


def _safe_slug(slug: str) -> str:
    return "".join(c for c in slug if c.isalnum() or c in "_-")


def main() -> None:
    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r and r[0]]

    if not slugs:
        print("Nincs tenant séma (public.tenants üres).")
        return

    for slug in slugs:
        safe = _safe_slug(slug)
        if safe != slug:
            print(f"Kihagyva (érvénytelen slug): {slug}")
            continue
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{safe}".kb_vector_outbox (
                    id SERIAL PRIMARY KEY,
                    kb_id INTEGER NOT NULL REFERENCES "{safe}".knowledge_bases(id) ON DELETE CASCADE,
                    source_point_id VARCHAR(36) NULL,
                    operation_type VARCHAR(48) NOT NULL,
                    payload JSON NOT NULL DEFAULT '{{}}',
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NULL,
                    next_retry_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    processed_at TIMESTAMP NULL
                )
            """))
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_kb_vector_outbox_status_next_retry
                ON "{safe}".kb_vector_outbox (status, next_retry_at)
            """))
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_kb_vector_outbox_kb_status
                ON "{safe}".kb_vector_outbox (kb_id, status)
            """))
            conn.commit()
        print(f"  {safe}.kb_vector_outbox kész")

    print("Kész.")


if __name__ == "__main__":
    main()
