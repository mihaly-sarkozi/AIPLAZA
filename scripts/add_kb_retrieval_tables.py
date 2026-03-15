#!/usr/bin/env python3
"""
Meglévő tenant sémákhoz retrieval/indexing táblák létrehozása.

Használat:
  python scripts/add_kb_retrieval_tables.py
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


def _create_tables_for_schema(conn, schema: str) -> None:
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_sentences (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NOT NULL,
            sentence_order INTEGER NOT NULL,
            text TEXT NOT NULL,
            sanitized_text TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            qdrant_point_id VARCHAR(64) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_entities (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NULL,
            canonical_name VARCHAR(512) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            aliases JSON NOT NULL DEFAULT '[]',
            confidence DOUBLE PRECISION NULL,
            first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_entity_aliases (
            id SERIAL PRIMARY KEY,
            entity_id INTEGER NOT NULL REFERENCES "{schema}".kb_entities(id) ON DELETE CASCADE,
            alias VARCHAR(512) NOT NULL
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_time_intervals (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NOT NULL,
            normalized_text VARCHAR(256) NOT NULL,
            valid_from TIMESTAMP NULL,
            valid_to TIMESTAMP NULL,
            granularity VARCHAR(32) NOT NULL DEFAULT 'unknown',
            confidence DOUBLE PRECISION NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_mentions (
            id SERIAL PRIMARY KEY,
            sentence_id INTEGER NOT NULL REFERENCES "{schema}".kb_sentences(id) ON DELETE CASCADE,
            surface_form VARCHAR(512) NOT NULL,
            mention_type VARCHAR(64) NOT NULL,
            grammatical_role VARCHAR(64) NULL,
            resolved_entity_id INTEGER NULL REFERENCES "{schema}".kb_entities(id) ON DELETE SET NULL,
            resolution_confidence DOUBLE PRECISION NULL,
            is_implicit_subject INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_assertions (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NOT NULL,
            source_document_title VARCHAR(512) NULL,
            source_sentence_id INTEGER NULL REFERENCES "{schema}".kb_sentences(id) ON DELETE SET NULL,
            subject_entity_id INTEGER NULL REFERENCES "{schema}".kb_entities(id) ON DELETE SET NULL,
            predicate VARCHAR(128) NOT NULL,
            object_entity_id INTEGER NULL REFERENCES "{schema}".kb_entities(id) ON DELETE SET NULL,
            object_value TEXT NULL,
            time_from TIMESTAMP NULL,
            time_to TIMESTAMP NULL,
            place_key VARCHAR(256) NULL,
            attributes JSON NOT NULL DEFAULT '[]',
            canonical_text TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            strength DOUBLE PRECISION NOT NULL DEFAULT 0.05,
            baseline_strength DOUBLE PRECISION NOT NULL DEFAULT 0.05,
            decay_rate DOUBLE PRECISION NOT NULL DEFAULT 0.015,
            reinforcement_count INTEGER NOT NULL DEFAULT 0,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_reinforced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            assertion_fingerprint VARCHAR(128) NOT NULL,
            qdrant_point_id VARCHAR(64) NULL
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_structural_chunks (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NOT NULL,
            chunk_order INTEGER NOT NULL,
            text TEXT NOT NULL,
            sentence_ids JSON NOT NULL DEFAULT '[]',
            token_count INTEGER NOT NULL DEFAULT 0,
            qdrant_point_id VARCHAR(64) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_assertion_evidence (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            assertion_id INTEGER NOT NULL REFERENCES "{schema}".kb_assertions(id) ON DELETE CASCADE,
            sentence_id INTEGER NOT NULL REFERENCES "{schema}".kb_sentences(id) ON DELETE CASCADE,
            source_point_id VARCHAR(36) NOT NULL,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".kb_reinforcement_events (
            id SERIAL PRIMARY KEY,
            kb_id INTEGER NOT NULL REFERENCES "{schema}".knowledge_bases(id) ON DELETE CASCADE,
            target_type VARCHAR(32) NOT NULL,
            target_id INTEGER NOT NULL,
            event_type VARCHAR(32) NOT NULL,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    conn.execute(text(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_entity_alias_entity_alias
        ON "{schema}".kb_entity_aliases(entity_id, alias)
    """))
    conn.execute(text(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_assertion_evidence_pair
        ON "{schema}".kb_assertion_evidence(assertion_id, sentence_id)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_fingerprint
        ON "{schema}".kb_assertions(kb_id, assertion_fingerprint)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_subject
        ON "{schema}".kb_assertions(kb_id, subject_entity_id)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_predicate
        ON "{schema}".kb_assertions(kb_id, predicate)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_time
        ON "{schema}".kb_assertions(kb_id, time_from, time_to)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_assertions_kb_place
        ON "{schema}".kb_assertions(kb_id, place_key)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_entities_kb_canonical_name
        ON "{schema}".kb_entities(kb_id, canonical_name)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_sentences_kb_source
        ON "{schema}".kb_sentences(kb_id, source_point_id)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_structural_chunks_kb_source
        ON "{schema}".kb_structural_chunks(kb_id, source_point_id)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_entity_aliases_alias
        ON "{schema}".kb_entity_aliases(alias)
    """))
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_kb_reinforce_kb_target
        ON "{schema}".kb_reinforcement_events(kb_id, target_type, target_id)
    """))


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
            _create_tables_for_schema(conn, safe)
            conn.commit()
        print(f"  {safe}: retrieval táblák készek")

    print("Kész.")


if __name__ == "__main__":
    main()
