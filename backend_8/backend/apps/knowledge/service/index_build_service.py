# backend/apps/knowledge/service/index_build_service.py
# Feladat: Knowledge index build lifecycle kezelese. Build utemezes, stale
# recovery, chunkolas, embedding/index upsert, retry es status frissites.

from __future__ import annotations

import asyncio
import time
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.index_profile import IndexProfile
from apps.knowledge.errors import KnowledgeBaseNotFound, KnowledgeIndexBuildConflict, KnowledgeIndexBuildNotFound
from apps.knowledge.service.chunking_service import ChunkingService
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.ports import (
    CorpusStorePort,
    IndexBuildStorePort,
    MetricsStorePort,
    SourceStorePort,
    VectorIndexFactory,
)
from apps.knowledge.service.retrieval_chunk_index_v0 import build_retrieval_chunk_index_rows
from apps.knowledge.service.semantic_block_index_v0 import build_semantic_block_index_rows
from apps.knowledge.training_ingest import build_sentence_rows


class IndexBuildService:
    def __init__(
        self,
        *,
        corpus_store: CorpusStorePort,
        source_store: SourceStorePort,
        index_build_store: IndexBuildStorePort,
        metrics_store: MetricsStorePort,
        vector_index_factory: VectorIndexFactory,
        chunking_service: ChunkingService,
        default_index_profile: Callable[[str | None], IndexProfile],
        vector_size_for_profile: Callable[[IndexProfile, Any], int | None],
        load_existing_retrieval_chunks: Callable[..., list[dict[str, Any]]],
        load_existing_semantic_blocks: Callable[..., list[dict[str, Any]]],
        log_step: Callable[..., None],
        index_build_lock: Callable[[str], threading.Lock],
        retry_count: int,
        retry_backoff_sec: float,
        stale_after_sec: int,
    ) -> None:
        self._corpus_store = corpus_store
        self._source_store = source_store
        self._index_build_store = index_build_store
        self._metrics_store = metrics_store
        self._vector_index_factory = vector_index_factory
        self._chunking_service = chunking_service
        self._default_index_profile = default_index_profile
        self._vector_size_for_profile = vector_size_for_profile
        self._load_existing_retrieval_chunks = load_existing_retrieval_chunks
        self._load_existing_semantic_blocks = load_existing_semantic_blocks
        self._log_step = log_step
        self._index_build_lock = index_build_lock
        self._retry_count = retry_count
        self._retry_backoff_sec = retry_backoff_sec
        self._stale_after_sec = stale_after_sec

    def schedule_index_build(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        index_profile_key: str,
        created_by: int | None,
    ) -> IndexBuild:
        profile = self._default_index_profile(index_profile_key)
        corpus = self._corpus_store.get_by_uuid(corpus_uuid)
        if not corpus:
            raise KnowledgeBaseNotFound()
        collection_name = f"{getattr(corpus, 'qdrant_collection_name')}__{profile.key}"
        build = IndexBuild(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            index_profile_key=profile.key,
            collection_name=collection_name,
            created_by=created_by,
            metadata={"source_count": len(self._source_store.list_for_corpus(corpus_uuid))},
        )
        self._metrics_store.increment("build_count", 1)
        self._log_step("build.start", status="pending", tenant=tenant, build_id=build.id, corpus_uuid=corpus_uuid, profile=profile.key)
        return self._index_build_store.create(build)

    def is_index_build_stale(self, build: IndexBuild) -> bool:
        if build.status != "building":
            return False
        reference = build.started_at or build.created_at
        if reference is None:
            return False
        return (_utcnow() - reference).total_seconds() >= self._stale_after_sec

    def mark_index_build_failed_as_stale(self, build_id: str, *, reason: str) -> IndexBuild:
        build = self._index_build_store.get(build_id)
        if build is None:
            raise KnowledgeIndexBuildNotFound()
        if build.status != "building":
            return build
        metadata = dict(build.metadata or {})
        metadata["stale_recovery_status"] = "failed"
        metadata["stale_recovery_reason"] = reason
        metadata["stale_recovery_at"] = _utcnow().isoformat()
        failed = self._index_build_store.update(
            replace(
                build,
                status="failed",
                error=reason,
                completed_at=_utcnow(),
                metadata=metadata,
            )
        )
        self._metrics_store.increment("build_failed_count", 1)
        self._log_step("build.stale_failed", status="error", tenant=failed.tenant, build_id=failed.id, error=reason)
        return failed

    async def run_index_build(self, build_id: str) -> IndexBuild:
        build = self._index_build_store.get(build_id)
        if build is None:
            raise KnowledgeIndexBuildNotFound()
        if build.status == "ready":
            return build
        if build.status == "building":
            raise KnowledgeIndexBuildConflict("Index build already in progress.")
        started = replace(build, status="building", started_at=_utcnow(), error=None)
        self._index_build_store.update(started)
        timer = time.perf_counter()
        try:
            sources = self._source_store.list_for_corpus(started.corpus_uuid)
            vector_index = self._vector_index_factory()
            profile = self._default_index_profile(started.index_profile_key)
            vector_size = self._vector_size_for_profile(profile, vector_index)
            started = self._index_build_store.update(
                replace(
                    started,
                    metadata={
                        **dict(started.metadata or {}),
                        "index_progress_state": "embedding_started",
                        "embedding_profile": profile.embedding_strategy,
                    },
                )
            )
            await vector_index.ensure_collection_schema_async(
                started.collection_name,
                vector_size=vector_size,
            )

            total_chunks = 0
            for source in sources:
                text = str(source.raw_content or "").strip()
                if not text:
                    continue
                self._index_build_store.update(
                    replace(
                        started,
                        metadata={
                            **dict(started.metadata or {}),
                            "index_progress_state": "embedding_batching",
                            "active_source_id": source.id,
                        },
                    )
                )
                chunks = self._chunking_service.build_chunks(text)
                total_chunks += len(chunks)
                rows = build_sentence_rows(chunks, source.title)
                for row in rows:
                    payload = row.setdefault("payload", {})
                    payload["source_id"] = source.id
                    payload["source_title"] = source.title
                    payload["build_id"] = started.id
                    payload["index_profile_key"] = profile.key
                self._index_build_store.update(
                    replace(
                        started,
                        metadata={
                            **dict(started.metadata or {}),
                            "index_progress_state": "embedding_upserting",
                            "active_source_id": source.id,
                        },
                    )
                )
                await vector_index.upsert_sentence_points(started.collection_name, rows)
                self._source_store.update(replace(source, status="ingested"))

            retrieval_chunks = self._load_existing_retrieval_chunks(
                corpus_uuid=started.corpus_uuid,
                exclude_interpretation_run_id=None,
            )
            retrieval_chunk_rows = build_retrieval_chunk_index_rows(
                retrieval_chunks,
                build_id=started.id,
                index_profile_key=profile.key,
            )
            upsert_retrieval_chunks = getattr(vector_index, "upsert_retrieval_chunk_points", None)
            if callable(upsert_retrieval_chunks) and retrieval_chunk_rows:
                await upsert_retrieval_chunks(started.collection_name, retrieval_chunk_rows)

            semantic_blocks = self._load_existing_semantic_blocks(
                corpus_uuid=started.corpus_uuid,
                exclude_interpretation_run_id=None,
            )
            semantic_block_rows = build_semantic_block_index_rows(
                semantic_blocks,
                build_id=started.id,
                index_profile_key=profile.key,
            )
            upsert_semantic_blocks = getattr(vector_index, "upsert_semantic_block_points", None)
            if callable(upsert_semantic_blocks) and semantic_block_rows:
                await upsert_semantic_blocks(started.collection_name, semantic_block_rows)

            finished = replace(
                started,
                status="ready",
                chunk_count=total_chunks,
                completed_at=_utcnow(),
                metadata={
                    **started.metadata,
                    "source_count": len(sources),
                    "profile_key": profile.key,
                    "embedding_strategy": profile.embedding_strategy,
                    "vector_size": vector_size,
                    "index_progress_state": "index_ready",
                    "retrieval_chunk_count": len(retrieval_chunk_rows),
                    "retrieval_chunk_indexed": bool(retrieval_chunk_rows),
                    "semantic_block_count": len(semantic_block_rows),
                    "semantic_block_indexed": bool(semantic_block_rows),
                },
            )
            self._index_build_store.update(finished)
            self._metrics_store.increment("build_success_count", 1)
            self._metrics_store.increment("chunk_count", total_chunks)
            self._metrics_store.record_timing("build_duration_ms", (time.perf_counter() - timer) * 1000.0)
            self._log_step(
                "build.ready",
                status="ok",
                tenant=finished.tenant,
                build_id=finished.id,
                duration_ms=(time.perf_counter() - timer) * 1000.0,
                chunk_count=total_chunks,
                source_count=len(sources),
            )
            return finished
        except Exception as exc:
            failed = replace(
                started,
                status="failed",
                error=str(exc),
                completed_at=_utcnow(),
                metadata={
                    **dict(started.metadata or {}),
                    "index_progress_state": "index_failed",
                },
            )
            self._index_build_store.update(failed)
            self._metrics_store.increment("build_failed_count", 1)
            self._log_step("build.failed", status="error", tenant=failed.tenant, build_id=failed.id, error=str(exc))
            raise

    async def run_index_build_with_retry(self, build_id: str) -> IndexBuild:
        lock = self._index_build_lock(build_id)
        if not lock.acquire(blocking=False):
            current = self._index_build_store.get(build_id)
            if current is None:
                raise KnowledgeIndexBuildNotFound()
            return current
        try:
            last_error: Exception | None = None
            for attempt in range(1, self._retry_count + 1):
                try:
                    return await self.run_index_build(build_id)
                except Exception as exc:
                    last_error = exc
                    if attempt >= self._retry_count:
                        raise
                    await asyncio.sleep(self._retry_backoff_sec * attempt)
            if last_error is not None:
                raise last_error
            raise KnowledgeIndexBuildConflict("Index build retry failed.")
        finally:
            lock.release()


__all__ = ["IndexBuildService"]
