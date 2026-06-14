from __future__ import annotations

from typing import Any

from sqlalchemy import text


def table_exists(db: Any, *, schema: str, table_name: str) -> bool:
    return bool(
        db.execute(
            text(
                """
                select 1
                from information_schema.tables
                where table_schema = :schema and table_name = :table_name
                """
            ),
            {"schema": schema, "table_name": table_name},
        ).scalar_one_or_none()
    )


def column_exists(db: Any, *, schema: str, table_name: str, column_name: str) -> bool:
    return bool(
        db.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema = :schema and table_name = :table_name and column_name = :column_name
                """
            ),
            {"schema": schema, "table_name": table_name, "column_name": column_name},
        ).scalar_one_or_none()
    )


def query_tenant_ingest_usage(db: Any) -> dict[str, int]:
    """Tenant-sémából aggregálja a kb_ingest_items tárhely- és karakterhasználatát."""

    schema = db.execute(text("select current_schema()")).scalar_one()
    has_kb_table = table_exists(db, schema=schema, table_name="knowledge_bases")
    has_items_table = table_exists(db, schema=schema, table_name="kb_ingest_items")
    if not has_kb_table or not has_items_table:
        return {"storage_bytes": 0, "trained_chars": 0}

    has_deleted_at = column_exists(db, schema=schema, table_name="knowledge_bases", column_name="deleted_at")
    deleted_filter = "AND kb.deleted_at IS NULL" if has_deleted_at else ""
    row = db.execute(
        text(
            f"""
            SELECT
                COALESCE(SUM(COALESCE(item.size_bytes, 0)), 0) AS storage_bytes,
                COALESCE(
                    SUM(
                        COALESCE(
                            NULLIF(item.metadata->>'char_count', '')::bigint,
                            0
                        )
                    ),
                    0
                ) AS trained_chars
            FROM kb_ingest_items item
            JOIN knowledge_bases kb ON kb.uuid = item.knowledge_base_id
            WHERE item.status NOT IN ('rejected', 'failed')
            {deleted_filter}
            """
        )
    ).mappings().first()
    if row is None:
        return {"storage_bytes": 0, "trained_chars": 0}
    return {
        "storage_bytes": int(row.get("storage_bytes") or 0),
        "trained_chars": int(row.get("trained_chars") or 0),
    }


__all__ = ["column_exists", "query_tenant_ingest_usage", "table_exists"]
