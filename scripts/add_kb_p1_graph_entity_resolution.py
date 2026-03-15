#!/usr/bin/env python3
"""
P1 javítások tenant sémákon:
- kb_mentions extra mezők (sentence_local_index, char span)
- kb_entities.canonical_key
- kb_assertions assertion_primary_subject_mention_id + subject_resolution_type
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
        f'ALTER TABLE "{schema}".kb_mentions ADD COLUMN IF NOT EXISTS sentence_local_index INTEGER NULL',
        f'ALTER TABLE "{schema}".kb_mentions ADD COLUMN IF NOT EXISTS char_start INTEGER NULL',
        f'ALTER TABLE "{schema}".kb_mentions ADD COLUMN IF NOT EXISTS char_end INTEGER NULL',
        f'ALTER TABLE "{schema}".kb_entities ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(512) NULL',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS assertion_primary_subject_mention_id INTEGER NULL',
        f'ALTER TABLE "{schema}".kb_assertions ADD COLUMN IF NOT EXISTS subject_resolution_type VARCHAR(16) NOT NULL DEFAULT \'explicit\'',
    ]
    for stmt in stmts:
        conn.execute(text(stmt))
    for stmt in [
        f'CREATE INDEX IF NOT EXISTS ix_kb_entities_canonical_key ON "{schema}".kb_entities(canonical_key)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_mentions_sentence_local_index ON "{schema}".kb_mentions(sentence_local_index)',
        f'CREATE INDEX IF NOT EXISTS ix_kb_assertions_subject_resolution_type ON "{schema}".kb_assertions(subject_resolution_type)',
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
        print(f"  {safe}: P1 patch kész")
    print("Kész.")


if __name__ == "__main__":
    main()
