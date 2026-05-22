# backend/core/modules/tenant/schema/ddl.py
# Feladat: Tenant schema DDL segédfüggvényeket tartalmaz. Táblák telepítését és schema-ra paraméterezett SQL statementek futtatását végzi tenant provisioning/migration folyamatokhoz. Tenant schema DDL adapter.
# Sárközi Mihály - 2026.05.21

"""Low-level DDL primitives for tenant schema management.

Responsibility: execute SQLAlchemy DDL (CREATE TABLE, ALTER TABLE, raw SQL
statements) inside a given schema.  No migration tracking, no orchestration.
"""
from __future__ import annotations

from sqlalchemy import MetaData, Table, text
from sqlalchemy.engine import Engine


def _commit_if_possible(conn) -> None:
    commit = getattr(conn, "commit", None)
    if callable(commit):
        commit()


def _safe_slug(slug: str) -> str:
    safe = "".join(c for c in slug if c.isalnum() or c in "_-")
    if safe != slug:
        raise ValueError(f"Érvénytelen tenant slug: {slug!r}")
    return safe


def install_schema_tables(engine: Engine, slug: str, tables: tuple[Table, ...] | list[Table]) -> None:
    """Create the given ORM tables inside the ``slug`` schema, respecting FK order."""
    temp_metadata = MetaData()
    copied: set[str] = set()

    def _copy_with_fk_deps(table: Table) -> None:
        key = table.fullname
        if key in copied:
            return
        copied.add(key)
        for fk in table.foreign_keys:
            referred = fk.column.table
            if referred.schema in (None, slug):
                _copy_with_fk_deps(referred)
        table.to_metadata(temp_metadata, schema=slug)

    for table in tables:
        _copy_with_fk_deps(table)
    temp_metadata.create_all(engine)


def run_schema_statements(
    engine: Engine,
    slug: str,
    statements: tuple[str, ...] | list[str],
) -> None:
    """Execute raw SQL statements substituting ``{schema}`` with ``slug``."""
    if not statements:
        return
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt.format(schema=slug)))
        _commit_if_possible(conn)


__all__ = [
    "_commit_if_possible",
    "_safe_slug",
    "install_schema_tables",
    "run_schema_statements",
]
