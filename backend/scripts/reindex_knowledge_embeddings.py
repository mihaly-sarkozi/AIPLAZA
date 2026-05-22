from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)


def _resolve_env_path() -> Path:
    candidates = (
        _project_root / ".env",
        _project_root.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _qdrant_client(settings) -> QdrantClient:
    kwargs: dict[str, object] = {"url": settings.qdrant_url, "check_compatibility": False}
    if str(settings.qdrant_api_key or "").strip():
        kwargs["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kwargs)


def _load_collections(conn, tenant_schema: str) -> list[str]:
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT collection_name
            FROM (
                SELECT qdrant_collection_name AS collection_name
                FROM "{tenant_schema}".knowledge_bases
                UNION ALL
                SELECT collection_name
                FROM "{tenant_schema}".knowledge_index_builds
            ) c
            WHERE collection_name IS NOT NULL
              AND collection_name <> ''
              AND collection_name LIKE 'kb\\_%' ESCAPE '\\'
            """
        )
    ).all()
    return sorted({str(row[0]).strip() for row in rows if str(row[0] or "").strip()})


def _reset_index_builds(conn, tenant_schema: str) -> int:
    result = conn.execute(text(f'DELETE FROM "{tenant_schema}".knowledge_index_builds'))
    return int(result.rowcount or 0)


def _reschedule_pending(conn, tenant_schema: str, *, profile_key: str, embedding_strategy: str) -> int:
    corpora = conn.execute(
        text(f'SELECT uuid, qdrant_collection_name FROM "{tenant_schema}".knowledge_bases WHERE deleted_at IS NULL')
    ).all()
    inserted = 0
    for corpus_uuid, base_collection in corpora:
        collection = f"{base_collection}__{profile_key}"
        conn.execute(
            text(
                f"""
                INSERT INTO "{tenant_schema}".knowledge_index_builds
                (id, corpus_uuid, index_profile_key, status, collection_name, chunk_count, error, metadata, created_at, created_by, started_at, completed_at)
                VALUES
                (:id, :corpus_uuid, :index_profile_key, 'pending', :collection_name, 0, NULL, :metadata::jsonb, NOW(), NULL, NULL, NULL)
                """
            ),
            {
                "id": str(uuid4()),
                "corpus_uuid": str(corpus_uuid),
                "index_profile_key": profile_key,
                "collection_name": collection,
                "metadata": (
                    '{"source":"reindex_knowledge_embeddings","embedding_strategy":"'
                    + embedding_strategy
                    + '"}'
                ),
            },
        )
        inserted += 1
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge Qdrant cleanup + reindex elokeszito script (dry-run tamogatassal).")
    parser.add_argument("--tenant-schema", required=True, help="Tenant schema nev, pl. demo")
    parser.add_argument("--dry-run", action="store_true", help="Csak listaz, nem modosit.")
    parser.add_argument("--reset-index-builds", action="store_true", help="Torli a knowledge_index_builds rekordokat.")
    parser.add_argument("--reschedule", action="store_true", help="Uj pending index buildeket hoz letre corpusonkent.")
    parser.add_argument("--profile-key", default="basic_chunk_v1", help="Ujrautemezes profile kulcs.")
    parser.add_argument("--embedding-strategy", default="local:BAAI/bge-m3", help="Metadata embedding strategy jeloles.")
    args = parser.parse_args()

    load_dotenv(_resolve_env_path())
    from core.kernel.config.config_loader import settings

    tenant_schema = str(args.tenant_schema).strip()
    if not tenant_schema:
        raise ValueError("tenant-schema kotelezo.")

    engine = create_engine(settings.database_url, future=True)
    qdrant = _qdrant_client(settings)

    with engine.begin() as conn:
        collections = _load_collections(conn, tenant_schema)
        print(f"[INFO] Tenant schema: {tenant_schema}")
        print(f"[INFO] Erintett kollekciok ({len(collections)}):")
        for name in collections:
            print(f"  - {name}")

        if args.dry_run:
            print("[DRY-RUN] Qdrant torles es DB modositas kihagyva.")
            return

        deleted_collections = 0
        for name in collections:
            try:
                if qdrant.collection_exists(collection_name=name):
                    qdrant.delete_collection(collection_name=name)
                    deleted_collections += 1
            except Exception as exc:
                print(f"[WARN] Kollekcio torles sikertelen: {name}: {exc}")
        print(f"[OK] Torolt Qdrant kollekciok: {deleted_collections}")

        if args.reset_index_builds:
            deleted_rows = _reset_index_builds(conn, tenant_schema)
            print(f"[OK] Torolt index build rekordok: {deleted_rows}")

        if args.reschedule:
            inserted = _reschedule_pending(
                conn,
                tenant_schema,
                profile_key=str(args.profile_key),
                embedding_strategy=str(args.embedding_strategy),
            )
            print(f"[OK] Uj pending index build rekordok: {inserted}")


if __name__ == "__main__":
    main()
