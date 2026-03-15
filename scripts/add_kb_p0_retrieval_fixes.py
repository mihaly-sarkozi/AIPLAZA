#!/usr/bin/env python3
"""
P0 retrieval javítások tenant sémákon:
- kb_sentences enrichment oszlopok
- kb_structural_chunks predicate_hints
- kb_assertion_evidence evidence_type + confidence

Használat:
  python scripts/add_kb_p0_retrieval_fixes.py
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
    for stmt in [
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS entity_ids JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS assertion_ids JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS predicate_hints JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS time_from TIMESTAMP NULL',
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS time_to TIMESTAMP NULL',
        f'ALTER TABLE "{schema}".kb_sentences ADD COLUMN IF NOT EXISTS place_keys JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_structural_chunks ADD COLUMN IF NOT EXISTS predicate_hints JSON NOT NULL DEFAULT \'[]\'',
        f'ALTER TABLE "{schema}".kb_assertion_evidence ADD COLUMN IF NOT EXISTS evidence_type VARCHAR(16) NOT NULL DEFAULT \'PRIMARY\'',
        f'ALTER TABLE "{schema}".kb_assertion_evidence ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NULL',
    ]:
        conn.execute(text(stmt))

    for stmt in [
        f'CREATE INDEX IF NOT EXISTS ix_kb_sentences_time_from ON "{schema}".kb_sentences(time_from)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_sentences_time_to ON "{schema}".kb_sentences(time_to)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertion_evidence_type ON "{schema}".kb_assertion_evidence(evidence_type)',
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
            _apply_patch(conn, safe)
            conn.commit()
        print(f"  {safe}: P0 retrieval patch kész")

    print("Kész.")


if __name__ == "__main__":
    main()
