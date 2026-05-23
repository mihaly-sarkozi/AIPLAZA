# backend/core/modules/tenant/service/schema_ddl.py
# Feladat: Kompatibilitási importútvonal a tenant schema DDL helper függvényekhez. A canonical implementáció a schema/ddl.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.ddl import (  # noqa: F401
    _commit_if_possible,
    _safe_slug,
    install_schema_tables,
    run_schema_statements,
)

__all__ = ["_commit_if_possible", "_safe_slug", "install_schema_tables", "run_schema_statements"]
