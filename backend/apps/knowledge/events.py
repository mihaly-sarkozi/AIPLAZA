from __future__ import annotations

from typing import Any

from apps.knowledge.api.background_jobs import (
    run_index_build_worker_task,
    run_recovery_sweep_for_tenant,
)
from apps.knowledge.bootstrap.service_keys import KNOWLEDGE_SERVICE
from apps.knowledge.ingest_jobs import process_ingest_run_and_start_index_sync
from core.kernel.http.app_dependencies import get_module_service
from core.modules.tenant.context.tenant_context import run_with_tenant_schema


def make_knowledge_ingest_pipeline_handler():
    def _handle(payload: dict[str, Any]) -> None:
        tenant_slug = payload.get("tenant_slug")
        run_id = str(payload.get("run_id") or "").strip()
        created_by = payload.get("created_by")
        if not run_id:
            raise ValueError("knowledge.ingest_pipeline payload missing run_id")
        process_ingest_run_and_start_index_sync(
            tenant_slug=tenant_slug if tenant_slug is None else str(tenant_slug),
            run_id=run_id,
            created_by=int(created_by) if created_by is not None else None,
        )

    return _handle


def make_knowledge_index_build_handler():
    def _handle(payload: dict[str, Any]) -> None:
        tenant_slug = payload.get("tenant_slug")
        build_id = str(payload.get("build_id") or "").strip()
        if not build_id:
            raise ValueError("knowledge.index_build payload missing build_id")
        facade = get_module_service(KNOWLEDGE_SERVICE)
        run_index_build_worker_task(
            tenant_slug=tenant_slug if tenant_slug is None else str(tenant_slug),
            facade=facade,
            build_id=build_id,
        )

    return _handle


def make_knowledge_ingest_item_reprocess_handler():
    def _handle(payload: dict[str, Any]) -> None:
        tenant_slug = payload.get("tenant_slug")
        item_id = str(payload.get("item_id") or "").strip()
        if not item_id:
            raise ValueError("knowledge.ingest_item_reprocess payload missing item_id")
        facade = get_module_service(KNOWLEDGE_SERVICE)
        run_with_tenant_schema(
            tenant_slug if tenant_slug is None else str(tenant_slug),
            facade.process_ingest_item,
            item_id,
        )

    return _handle


def make_knowledge_recovery_sweep_handler():
    def _handle(payload: dict[str, Any]) -> None:
        tenant_slug = payload.get("tenant_slug")
        facade = get_module_service(KNOWLEDGE_SERVICE)
        run_with_tenant_schema(
            tenant_slug if tenant_slug is None else str(tenant_slug),
            run_recovery_sweep_for_tenant,
            tenant_slug if tenant_slug is None else str(tenant_slug),
            facade,
            None,
        )

    return _handle


def register_knowledge_event_handlers(dispatcher: Any) -> None:
    dispatcher.register("knowledge.ingest_pipeline", make_knowledge_ingest_pipeline_handler())
    dispatcher.register("knowledge.index_build", make_knowledge_index_build_handler())
    dispatcher.register("knowledge.ingest_item_reprocess", make_knowledge_ingest_item_reprocess_handler())
    dispatcher.register("knowledge.recovery_sweep", make_knowledge_recovery_sweep_handler())

