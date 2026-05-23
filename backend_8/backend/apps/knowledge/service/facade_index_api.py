from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class IndexFacadeMixin:
    def schedule_index_build(self, *, tenant: str, corpus_uuid: str, index_profile_key: str, created_by: int | None) -> IndexBuild:
        return self._index_build_service.schedule_index_build(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            index_profile_key=index_profile_key,
            created_by=created_by,
        )

    def get_index_build(self, build_id: str) -> IndexBuild | None:
        return self._index_build_store.get(build_id)

    def list_index_builds(self, corpus_uuid: str) -> list[IndexBuild]:
        return self._index_build_store.list_for_corpus(corpus_uuid)

    def is_ingest_run_stale(self, run: IngestRun) -> bool:
        if run.status not in {"queued", "processing"}:
            return False
        reference = run.updated_at or run.started_at or run.created_at
        if reference is None:
            return False
        return (_utcnow() - reference).total_seconds() >= self._STALE_INGEST_RUN_FAIL_AFTER_SEC

    def mark_ingest_run_failed_as_stale(self, run_id: str, *, reason: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise IngestRunNotFound()
        if run.status not in {"queued", "processing"}:
            return run
        metadata = dict(run.metadata or {})
        metadata["stale_recovery_status"] = "failed"
        metadata["stale_recovery_reason"] = reason
        metadata["stale_recovery_at"] = _utcnow().isoformat()
        failed = self._ingest_run_store.update(
            replace(
                run,
                status="failed",
                completed_at=_utcnow(),
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )
        self._record_ingest_event(
            run_id=failed.id,
            event_type="run_stale_failed",
            status="failed",
            message=reason,
        )
        return failed

    def mark_ingest_run_enqueue_failed(self, run_id: str, *, reason: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise IngestRunNotFound()
        metadata = dict(run.metadata or {})
        metadata["enqueue_status"] = "failed"
        metadata["enqueue_error"] = reason
        metadata["enqueue_failed_at"] = _utcnow().isoformat()
        failed = self._ingest_run_store.update(
            replace(
                run,
                status="failed",
                queued_count=0,
                processing_count=0,
                failed_count=max(1, int(run.batch_size or 1)),
                completed_at=_utcnow(),
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )
        self._record_ingest_event(
            run_id=failed.id,
            event_type="enqueue_failed",
            status="failed",
            message=reason,
        )
        return failed

    def is_index_build_stale(self, build: IndexBuild) -> bool:
        return self._index_build_service.is_index_build_stale(build)

    def mark_index_build_failed_as_stale(self, build_id: str, *, reason: str) -> IndexBuild:
        return self._index_build_service.mark_index_build_failed_as_stale(build_id, reason=reason)

    async def run_index_build(self, build_id: str) -> IndexBuild:
        return await self._index_build_service.run_index_build(build_id)

    async def run_index_build_with_retry(self, build_id: str) -> IndexBuild:
        return await self._index_build_service.run_index_build_with_retry(build_id)

    def _resolve_builds(self, *, corpus_uuid: str, build_ids: list[str] | None = None) -> list[IndexBuild]:
        return self._retrieval_service._builds().resolve_builds(corpus_uuid=corpus_uuid, build_ids=build_ids)

    async def _retrieve_hits_with_resilience(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self._retrieval_service._retrieval_engine = self._retrieval_engine
        return await self._retrieval_service.retrieve_hits_with_resilience(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            builds=builds,
            retrieval_profile=retrieval_profile,
            query_profile=query_profile,
        )


__all__ = ["IndexFacadeMixin"]
