from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.kernel.interface.app_keys import MODULE_KNOWLEDGE_SERVICE
from core.kernel.http.app_dependencies import get_module_service
from core.modules.tenant.context.tenant_context import run_with_tenant_schema

logger = logging.getLogger(__name__)


def process_ingest_run_and_start_index_sync(
    *,
    tenant_slug: str | None,
    run_id: str,
    created_by: int | None,
    facade: Any | None = None,
) -> None:
    effective_facade = facade or get_module_service(MODULE_KNOWLEDGE_SERVICE)
    completed = run_with_tenant_schema(
        tenant_slug,
        effective_facade.process_ingest_run,
        run_id,
        auto_refresh_semantic_index=False,
    )
    if completed.status not in {"completed", "partial_success"} or completed.completed_count <= 0:
        return
    build = effective_facade.schedule_index_build(
        tenant=completed.tenant,
        corpus_uuid=completed.corpus_uuid,
        index_profile_key="basic_chunk_v1",
        created_by=created_by,
    )
    from apps.knowledge.api.background_jobs import enqueue_index_build_job

    enqueue_index_build_job(tenant_slug=tenant_slug, build_id=build.id)


async def process_ingest_run_and_start_index_async(
    *,
    tenant_slug: str | None,
    run_id: str,
    created_by: int | None,
    facade: Any | None = None,
) -> None:
    try:
        await asyncio.to_thread(
            process_ingest_run_and_start_index_sync,
            tenant_slug=tenant_slug,
            run_id=run_id,
            created_by=created_by,
            facade=facade,
        )
    except Exception:
        logger.exception(
            "Automatic index build after ingest failed",
            extra={"run_id": run_id, "tenant_slug": tenant_slug},
        )
