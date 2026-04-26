# Backward-compat re-export – implementation moved to service/schema/ddl.py
from core.extensions.tenant.schema.ddl import (  # noqa: F401
    _commit_if_possible,
    _safe_slug,
    install_schema_tables,
    run_schema_statements,
)

__all__ = ["_commit_if_possible", "_safe_slug", "install_schema_tables", "run_schema_statements"]
