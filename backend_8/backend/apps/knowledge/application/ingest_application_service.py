# backend/apps/knowledge/application/ingest_application_service.py
# Feladat: Knowledge ingest use-case orchestrationt tartalmaz. A router HTTP-adapter marad, ez a service pedig a facade ingest run létrehozását, outbox queue-ba helyezést és sikertelen enqueue esetén a run státuszának lezárását koordinálja. Első lépés a KnowledgeFacade mega-osztály application service-ekre bontásában.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from typing import Any

from apps.knowledge.api.background_jobs import enqueue_ingest_pipeline_job


class IngestQueueUnavailableError(RuntimeError):
    pass


class KnowledgeIngestApplicationService:
    def __init__(self, facade: Any) -> None:
        self._facade = facade

    def create_text_run_and_enqueue(
        self,
        *,
        tenant_slug: str | None,
        corpus_uuid: str,
        title: str,
        text: str,
        created_by: int | None,
    ):
        run = self._facade.create_text_ingest_run(
            tenant=tenant_slug or "",
            corpus_uuid=corpus_uuid,
            title=title,
            text=text,
            created_by=created_by,
        )
        self.enqueue_run(
            tenant_slug=tenant_slug,
            run_id=run.id,
            created_by=created_by,
        )
        return run

    def create_file_run_and_enqueue(
        self,
        *,
        tenant_slug: str | None,
        corpus_uuid: str,
        files: list[dict[str, Any]],
        created_by: int | None,
    ):
        run = self._facade.create_file_ingest_run(
            tenant=tenant_slug or "",
            corpus_uuid=corpus_uuid,
            files=files,
            created_by=created_by,
        )
        self.enqueue_run(
            tenant_slug=tenant_slug,
            run_id=run.id,
            created_by=created_by,
        )
        return run

    def create_url_run_and_enqueue(
        self,
        *,
        tenant_slug: str | None,
        corpus_uuid: str,
        urls: list[dict[str, Any]],
        created_by: int | None,
    ):
        run = self._facade.create_url_ingest_run(
            tenant=tenant_slug or "",
            corpus_uuid=corpus_uuid,
            urls=urls,
            created_by=created_by,
        )
        self.enqueue_run(
            tenant_slug=tenant_slug,
            run_id=run.id,
            created_by=created_by,
        )
        return run

    def enqueue_run(
        self,
        *,
        tenant_slug: str | None,
        run_id: str,
        created_by: int | None,
    ) -> None:
        try:
            enqueue_ingest_pipeline_job(
                tenant_slug=tenant_slug,
                run_id=run_id,
                created_by=created_by,
                facade=self._facade,
            )
        except Exception as exc:
            marker = getattr(self._facade, "mark_ingest_run_enqueue_failed", None)
            if callable(marker):
                marker(run_id, reason=str(exc))
            raise IngestQueueUnavailableError("Knowledge ingest worker queue is not available.") from exc
