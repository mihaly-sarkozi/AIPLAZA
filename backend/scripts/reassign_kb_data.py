#!/usr/bin/env python3
"""Tenant sémában knowledge_base_id átírása (orphan feldolgozási adat javítása).

Használat:
  python3 scripts/reassign_kb_data.py --tenant mihaly2 --from f401f7ae-... --to 9bb1a3d0-...
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from core.kernel.config.config_loader import settings
from core.kernel.db.session import make_session_factory


_TABLES_WITH_KB_ID = (
    "kb_ingest_batches",
    "kb_ingest_items",
    "kb_understanding_jobs",
    "kb_extracted_content",
    "kb_extracted_content_parts",
    "kb_normalized_content",
    "kb_normalized_content_parts",
    "kb_chunks",
    "kb_discovery_jobs",
    "kb_enrichments",
    "kb_entities",
    "kb_entity_mentions",
    "kb_keywords",
    "kb_topics",
    "kb_temporal_mentions",
    "kb_spatial_mentions",
    "kb_process_mentions",
    "kb_relationships",
    "kb_scores",
    "kb_embedding_jobs",
    "kb_embeddings",
    "kb_indexing_jobs",
    "kb_indexed_chunks",
    "kb_processing_events",
    "kb_processing_issues",
    "kb_processing_metrics",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reassign knowledge_base_id across KB tables")
    parser.add_argument("--tenant", required=True, help="Tenant schema slug (pl. mihaly2)")
    parser.add_argument("--from", dest="from_id", required=True, help="Régi knowledge base UUID")
    parser.add_argument("--to", dest="to_id", required=True, help="Új knowledge base UUID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    schema = args.tenant.strip()
    from_id = args.from_id.strip()
    to_id = args.to_id.strip()
    if from_id == to_id:
        print("from és to azonos — nincs mit csinálni")
        return 0

    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        for table in _TABLES_WITH_KB_ID:
            count = session.execute(
                text(
                    f"SELECT COUNT(*) FROM \"{schema}\".{table} "
                    "WHERE knowledge_base_id = :from_id"
                ),
                {"from_id": from_id},
            ).scalar_one()
        if int(count or 0) == 0:
            continue
        print(f"{table}: {count} sor")
        if not args.dry_run:
            if table == "kb_processing_metrics":
                session.execute(
                    text(
                        f"DELETE FROM \"{schema}\".{table} "
                        "WHERE knowledge_base_id = :to_id"
                    ),
                    {"to_id": to_id},
                )
            session.execute(
                    text(
                        f"UPDATE \"{schema}\".{table} "
                        "SET knowledge_base_id = :to_id "
                        "WHERE knowledge_base_id = :from_id"
                    ),
                    {"from_id": from_id, "to_id": to_id},
                )
        if not args.dry_run:
            session.commit()
            print("Kész.")
        else:
            print("Dry-run — nincs módosítás.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
