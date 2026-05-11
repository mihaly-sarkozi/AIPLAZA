from __future__ import annotations

from typing import Any

from apps.knowledge.ingest_jobs import process_ingest_run_and_start_index_sync


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


def register_knowledge_event_handlers(dispatcher: Any) -> None:
    dispatcher.register("knowledge.ingest_pipeline", make_knowledge_ingest_pipeline_handler())

