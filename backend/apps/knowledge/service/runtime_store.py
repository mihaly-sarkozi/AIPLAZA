from __future__ import annotations

from dataclasses import replace
from statistics import mean
from threading import Lock
from typing import Any

from apps.knowledge.domain.context_profile import DEFAULT_CONTEXT_PROFILE, ContextProfile
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.index_profile import DEFAULT_INDEX_PROFILE, IndexProfile
from apps.knowledge.domain.query_run import QueryRun
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE, RetrievalProfile
from apps.knowledge.domain.source import Source


class InMemorySourceStore:
    def __init__(self) -> None:
        self._items: dict[str, Source] = {}
        self._lock = Lock()

    def create(self, source: Source) -> Source:
        with self._lock:
            self._items[source.id] = source
        return source

    def list_for_corpus(self, corpus_uuid: str) -> list[Source]:
        with self._lock:
            return [item for item in self._items.values() if item.corpus_uuid == corpus_uuid]

    def get(self, source_id: str) -> Source | None:
        with self._lock:
            return self._items.get(source_id)

    def update(self, source: Source) -> Source:
        with self._lock:
            self._items[source.id] = source
        return source


class InMemoryIndexProfileStore:
    def __init__(self) -> None:
        self._items: dict[str, IndexProfile] = {
            DEFAULT_INDEX_PROFILE.key: DEFAULT_INDEX_PROFILE,
            "hybrid_v1": IndexProfile(
                key="hybrid_v1",
                chunking_rule="sentence+window",
                embedding_strategy="openai:text-embedding-3-large",
                index_type="qdrant_dense+lexical",
                metadata_mode="source_payload",
                config={"fusion": "semantic_lexical"},
            ),
        }

    def get(self, key: str) -> IndexProfile | None:
        return self._items.get(key)

    def list_all(self) -> list[IndexProfile]:
        return list(self._items.values())


class InMemoryIndexBuildStore:
    def __init__(self) -> None:
        self._items: dict[str, IndexBuild] = {}
        self._lock = Lock()

    def create(self, build: IndexBuild) -> IndexBuild:
        with self._lock:
            self._items[build.id] = build
        return build

    def update(self, build: IndexBuild) -> IndexBuild:
        with self._lock:
            self._items[build.id] = build
        return build

    def get(self, build_id: str) -> IndexBuild | None:
        with self._lock:
            return self._items.get(build_id)

    def list_for_corpus(self, corpus_uuid: str) -> list[IndexBuild]:
        with self._lock:
            items = [item for item in self._items.values() if item.corpus_uuid == corpus_uuid]
        return sorted(items, key=lambda item: item.created_at, reverse=True)


class InMemoryQueryRunStore:
    def __init__(self) -> None:
        self._items: list[QueryRun] = []
        self._lock = Lock()

    def get(self, query_run_id: str) -> QueryRun | None:
        with self._lock:
            return next((item for item in self._items if item.id == query_run_id), None)

    def save(self, run: QueryRun) -> QueryRun:
        with self._lock:
            self._items.append(run)
        return run

    def list_recent(self, *, corpus_uuid: str | None = None, limit: int = 20) -> list[QueryRun]:
        with self._lock:
            items = list(self._items)
        if corpus_uuid:
            items = [item for item in items if item.corpus_uuid == corpus_uuid]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]


class InMemoryMetricsStore:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._timings: dict[str, list[float]] = {}
        self._lock = Lock()

    def increment(self, metric: str, value: int = 1) -> None:
        with self._lock:
            self._counters[metric] = self._counters.get(metric, 0) + value

    def record_timing(self, metric: str, value_ms: float) -> None:
        with self._lock:
            self._timings.setdefault(metric, []).append(float(value_ms))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
            timings = {
                key: {
                    "count": len(values),
                    "avg_ms": round(mean(values), 2) if values else 0.0,
                    "max_ms": round(max(values), 2) if values else 0.0,
                }
                for key, values in self._timings.items()
            }
        return {"counters": counters, "timings": timings}


class SimpleChunkBuilder:
    def build_chunks(self, text: str) -> list[str]:
        from shared.text.chunking import chunk_text_for_training

        return chunk_text_for_training(text)


class SimpleRetrievalEngine:
    def __init__(self, vector_index_factory) -> None:
        self._vector_index_factory = vector_index_factory

    async def retrieve(
        self,
        *,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        payload_filter = _payload_filter_from_query_profile(query_profile or {})
        semantic_block_filter = _semantic_block_payload_filter_from_query_profile(query_profile or {})
        for build in builds:
            vector_index = self._vector_index_factory()
            rows: list[dict[str, Any]] = []
            if semantic_block_filter:
                rows = await vector_index.search_points(
                    collection=build.collection_name,
                    query=query,
                    limit=retrieval_profile.top_k,
                    point_types=["semantic_block"],
                    payload_filter=semantic_block_filter,
                    lexical_query=query,
                )
            if not rows:
                rows = await vector_index.search_points(
                    collection=build.collection_name,
                    query=query,
                    limit=retrieval_profile.top_k,
                    point_types=["semantic_block"],
                    lexical_query=query,
                )
            if not rows:
                rows = await vector_index.search_points(
                    collection=build.collection_name,
                    query=query,
                    limit=retrieval_profile.top_k,
                    point_types=["retrieval_chunk"],
                    payload_filter=payload_filter,
                    lexical_query=query,
                )
            if not rows and payload_filter:
                rows = await vector_index.search_points(
                    collection=build.collection_name,
                    query=query,
                    limit=retrieval_profile.top_k,
                    point_types=["retrieval_chunk"],
                    lexical_query=query,
                )
            if not rows:
                rows = await vector_index.search_points(
                    collection=build.collection_name,
                    query=query,
                    limit=retrieval_profile.top_k,
                    point_types=["sentence"],
                    lexical_query=query,
                )
            rows = _apply_block_quality_scores(rows)
            for row in rows:
                payload = dict(row.get("payload") or {})
                row["build_id"] = build.id
                row["build_key"] = build.index_profile_key
                row["payload"] = payload
                hits.append(row)
        return hits


def _payload_filter_from_query_profile(query_profile: dict[str, Any]) -> dict[str, Any]:
    payload_filter: dict[str, Any] = {}
    entity_type = str(query_profile.get("entity_type") or "").strip()
    if entity_type:
        payload_filter["entity_type"] = entity_type
    state = str(query_profile.get("state") or "").strip()
    if state:
        payload_filter["states"] = [state]
    time_filter = str(query_profile.get("time_filter") or "").strip()
    if time_filter:
        payload_filter["time_modes"] = [time_filter]
    return payload_filter


def _semantic_block_payload_filter_from_query_profile(query_profile: dict[str, Any]) -> dict[str, Any]:
    payload_filter: dict[str, Any] = {}
    time_filter = str(query_profile.get("time_filter") or "").strip()
    if time_filter:
        payload_filter["time_modes"] = [time_filter]
    return payload_filter


def _apply_block_quality_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.get("payload") or {})
        if payload.get("point_type") != "semantic_block":
            adjusted.append(row)
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        status = str(payload.get("block_status") or metadata.get("block_status") or "").strip().lower()
        quality = metadata.get("block_quality") if isinstance(metadata.get("block_quality"), dict) else {}
        active = bool(quality.get("active_for_retrieval", status not in {"rejected", "withdrawn"}))
        if status in {"rejected", "withdrawn"} or not active:
            continue
        retrieval_weight = float(payload.get("retrieval_weight") or metadata.get("retrieval_weight") or quality.get("retrieval_weight") or 1.0)
        base_score = float(row.get("fusion_score") or row.get("score") or 0.0)
        adjusted_score = max(0.0, min(1.0, base_score * max(0.0, retrieval_weight)))
        next_row = dict(row)
        next_payload = dict(payload)
        next_payload["quality_score_explanation"] = {
            "base_score": round(base_score, 4),
            "retrieval_weight": round(retrieval_weight, 4),
            "adjusted_score": round(adjusted_score, 4),
            "block_status": status or "draft",
            "source_reliability": payload.get("source_reliability") or metadata.get("source_reliability"),
            "conflict_count": payload.get("conflict_count") or metadata.get("conflict_count") or 0,
        }
        next_row["payload"] = next_payload
        next_row["fusion_score"] = adjusted_score
        adjusted.append(next_row)
    return sorted(adjusted, key=lambda item: float(item.get("fusion_score") or item.get("score") or 0.0), reverse=True)


class SimpleContextBuilder:
    def build_context(
        self,
        *,
        query: str,
        hits: list[dict[str, Any]],
        context_profile: ContextProfile,
        query_run_id: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        dedupe_keys: set[str] = set()
        selected: list[dict[str, Any]] = []
        parts: list[str] = []
        total_chars = 0

        ordered_hits = sorted(hits, key=lambda item: float(item.get("fusion_score") or item.get("score") or 0.0), reverse=True)
        for item in ordered_hits:
            payload = dict(item.get("payload") or {})
            snippet = str(payload.get("text") or "").strip()
            if not snippet:
                continue
            dedupe_key = snippet if context_profile.deduplicate else f"{item.get('build_id')}:{item.get('id')}"
            if dedupe_key in dedupe_keys:
                continue
            next_size = total_chars + len(snippet)
            if len(selected) >= context_profile.max_chunks or next_size > context_profile.max_context_chars:
                break
            dedupe_keys.add(dedupe_key)
            selected.append(item)
            parts.append(snippet)
            total_chars = next_size

        context_text = "\n\n".join(parts)
        return context_text, selected[: context_profile.citation_limit]


def default_retrieval_profile() -> RetrievalProfile:
    return DEFAULT_RETRIEVAL_PROFILE


def default_context_profile() -> ContextProfile:
    return DEFAULT_CONTEXT_PROFILE


__all__ = [
    "InMemoryIndexBuildStore",
    "InMemoryIndexProfileStore",
    "InMemoryMetricsStore",
    "InMemoryQueryRunStore",
    "InMemorySourceStore",
    "SimpleChunkBuilder",
    "SimpleContextBuilder",
    "SimpleRetrievalEngine",
    "default_context_profile",
    "default_retrieval_profile",
]
