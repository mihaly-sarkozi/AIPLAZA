#!/usr/bin/env python3
"""
P4 domain/storage hardening tenant sémákon:
- kb_assertion_relations.relation_confidence
- kb_places.place_type + country_code
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


def _apply_patch(conn, schema: str) -> None:
    stmts = [
        f'ALTER TABLE "{schema}".kb_assertion_relations ADD COLUMN IF NOT EXISTS relation_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0',
        f'ALTER TABLE "{schema}".kb_places ADD COLUMN IF NOT EXISTS place_type VARCHAR(64) NULL',
        f'ALTER TABLE "{schema}".kb_places ADD COLUMN IF NOT EXISTS country_code VARCHAR(8) NULL',
    ]
    for stmt in stmts:
        conn.execute(text(stmt))
    for stmt in [
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertion_relations_relation_confidence ON "{schema}".kb_assertion_relations(relation_confidence)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_places_place_type ON "{schema}".kb_places(place_type)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_places_country_code ON "{schema}".kb_places(country_code)',
    ]:
        conn.execute(text(stmt))


def main() -> None:
    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r and r[0]]

    for slug in slugs:
        safe = _safe_slug(slug)
        if safe != slug:
            print(f"Kihagyva (érvénytelen slug): {slug}")
            continue
        with engine.connect() as conn:
            _apply_patch(conn, safe)
            conn.commit()
        print(f"  {safe}: P4 domain/storage patch kész")
    print("Kész.")


if __name__ == "__main__":
    main()
