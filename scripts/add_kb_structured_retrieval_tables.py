#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz a strukturált retrieval bővítések felvétele.

Használat:
  python scripts/add_kb_structured_retrieval_tables.py
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


def _apply_schema_patch(conn, schema: str) -> None:
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_places (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            canonical_name VARCHAR(256) NOT NULL,
            normalized_key VARCHAR(256) NOT NULL,
            parent_place_id INTEGER NULL REFERENCES "{schema}".kb_places(id) ON DELETE SET NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_assertion_relations (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            from_assertion_id INTEGER NOT NULL REFERENCES "{schema}".kb_assertions(id) ON DELETE CASCADE,
            to_assertion_id INTEGER NOT NULL REFERENCES "{schema}".kb_assertions(id) ON DELETE CASCADE,
            relation_type VARCHAR(64) NOT NULL,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # Új oszlopok meglévő táblákon (idempotens).
    for stmt in [
        f'ALTER TABLE "{schema}".kb_entity_aliases ADD COLUMN IF NOT EXISTS alias_text VARCHAR(512)',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS time_interval_id INTEGER',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS place_id INTEGER',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS modality VARCHAR(32) NOT NULL DEFAULT \'asserted\'',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS polarity VARCHAR(32) NOT NULL DEFAULT \'positive\'',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS source_diversity INTEGER NOT NULL DEFAULT 1',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS source_time TIMESTAMP NULL',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS ingest_time TIMESTAMP NOT NULL DEFAULT NOW()',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS assertion_ids JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS entity_ids JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS time_from TIMESTAMP NULL',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS time_to TIMESTAMP NULL',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS place_keys JSON NOT NULL DEFAULT \'[]\'',
    ]:
        conn.execute(text(stmt))

    for stmt in [
        f'CREATE INDEX IF NOT EXISTS ix_kb_places_kb_name ON "{schema}".kb_places(kb_id, canonical_name)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_places_kb_key ON "{schema}".kb_places(kb_id, normalized_key)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_entity_aliases_entity_alias_text ON "{schema}".kb_entity_aliases(entity_id, alias_text)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_time_interval ON "{schema}".kb_assertions(kb_id, time_interval_id)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_source ON "{schema}".kb_assertions(kb_id, source_point_id)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertion_rel_kb_from ON "{schema}".kb_assertion_relations(kb_id, from_assertion_id)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertion_rel_kb_to ON "{schema}".kb_assertion_relations(kb_id, to_assertion_id)',
    ]:
        conn.execute(text(stmt))


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
            _apply_schema_patch(conn, safe)
            conn.commit()
        print(f"  {safe}: structured retrieval patch kész")

    print("Kész.")


if __name__ == "__main__":
    main()
