#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz idempotency_key oszlop hozzáadása a kb_training_log táblához.

Használat:
  python scripts/add_kb_training_idempotency_key.py
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
                ALTER TABLE "{safe}".kb_training_log
                ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128) NULL
            """))
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_kb_training_log_idempotency_key
                ON "{safe}".kb_training_log (idempotency_key)
            """))
            conn.commit()
        print(f"  {safe}.kb_training_log: idempotency_key készen")

    print("Kész.")


if __name__ == "__main__":
    main()
