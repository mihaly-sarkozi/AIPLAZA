from __future__ import annotations

from apps.kb.kb_search.orm.SearchCitation import SearchCitation
from apps.kb.kb_search.orm.SearchContextBlock import SearchContextBlock
from apps.kb.kb_search.orm.SearchQueryResult import SearchQueryResult
from apps.kb.kb_search.orm.SearchQueryRun import SearchQueryRun
from core.modules.tenant.service import TenantSchemaHook, install_schema_tables, register_tenant_schema_hooks


def _install_kb_search_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            SearchQueryRun.__table__,
            SearchQueryResult.__table__,
            SearchContextBlock.__table__,
            SearchCitation.__table__,
        ),
    )


def register_kb_search_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_search",
                revision="kb.search.schema.v1",
                install=_install_kb_search_schema,
                table_names=(
                    "kb_search_query_runs",
                    "kb_search_query_results",
                    "kb_search_context_blocks",
                    "kb_search_citations",
                ),
            )
        ]
    )


__all__ = ["register_kb_search_tenant_hooks"]
