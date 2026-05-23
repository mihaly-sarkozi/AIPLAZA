from __future__ import annotations

from sqlalchemy import delete, select

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.query_run import Citation, QueryRun
from apps.knowledge.domain.source import Source
from apps.knowledge.models import (
    KnowledgeIndexBuildORM,
    KnowledgeQueryRunORM,
    KnowledgeSourceORM,
)


def _source_to_domain(row: KnowledgeSourceORM) -> Source:
    return Source(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        title=row.title,
        source_type=row.source_type,  # type: ignore[arg-type]
        raw_content=row.raw_content,
        file_ref=row.file_ref,
        status=row.status,  # type: ignore[arg-type]
        created_by=row.created_by,
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


def _build_to_domain(row: KnowledgeIndexBuildORM) -> IndexBuild:
    return IndexBuild(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        index_profile_key=row.index_profile_key,
        status=row.status,  # type: ignore[arg-type]
        collection_name=row.collection_name,
        chunk_count=row.chunk_count,
        error=row.error,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        metadata=dict(row.metadata_json or {}),
    )


def _query_run_to_domain(row: KnowledgeQueryRunORM) -> QueryRun:
    citations = [
        Citation(
            source_id=str(item.get("source_id") or ""),
            build_id=str(item.get("build_id") or ""),
            snippet=str(item.get("snippet") or ""),
            score=float(item.get("score") or 0.0),
            title=item.get("title"),
            chunk_id=item.get("chunk_id"),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in (row.citations or [])
    ]
    return QueryRun(
        id=row.id,
        tenant="",
        query=row.query_text,
        corpus_uuid=row.corpus_uuid,
        build_ids=[str(item) for item in (row.build_ids or [])],
        retrieval_profile_key=row.retrieval_profile_key,
        context_profile_key=row.context_profile_key,
        latency_ms=float(row.latency_ms or 0.0),
        result_count=int(row.result_count or 0),
        citations=citations,
        context_text=row.context_text or "",
        feedback=row.feedback,
        compare_mode=bool(row.compare_mode),
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


class SQLAlchemySourceStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, source: Source) -> Source:
        with self._sf() as session:
            row = KnowledgeSourceORM(
                id=source.id,
                corpus_uuid=source.corpus_uuid,
                title=source.title,
                source_type=source.source_type,
                raw_content=source.raw_content,
                file_ref=source.file_ref,
                status=source.status,
                metadata_json=dict(source.metadata or {}),
                created_at=source.created_at,
                created_by=source.created_by,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _source_to_domain(row)

    def list_for_corpus(self, corpus_uuid: str) -> list[Source]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeSourceORM)
                .where(KnowledgeSourceORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeSourceORM.created_at.asc())
            ).scalars().all()
            return [_source_to_domain(row) for row in rows]

    def get(self, source_id: str) -> Source | None:
        with self._sf() as session:
            row = session.get(KnowledgeSourceORM, source_id)
            return _source_to_domain(row) if row else None

    def update(self, source: Source) -> Source:
        with self._sf() as session:
            row = session.get(KnowledgeSourceORM, source.id)
            if row is None:
                raise ValueError(f"Knowledge source not found: {source.id}")
            row.title = source.title
            row.raw_content = source.raw_content
            row.file_ref = source.file_ref
            row.status = source.status
            row.metadata_json = dict(source.metadata or {})
            session.commit()
            session.refresh(row)
            return _source_to_domain(row)

    def delete(self, source_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSourceORM).where(KnowledgeSourceORM.id == source_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSourceORM).where(KnowledgeSourceORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyIndexBuildStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, build: IndexBuild) -> IndexBuild:
        with self._sf() as session:
            row = KnowledgeIndexBuildORM(
                id=build.id,
                corpus_uuid=build.corpus_uuid,
                index_profile_key=build.index_profile_key,
                status=build.status,
                collection_name=build.collection_name,
                chunk_count=build.chunk_count,
                error=build.error,
                metadata_json=dict(build.metadata or {}),
                created_at=build.created_at,
                created_by=build.created_by,
                started_at=build.started_at,
                completed_at=build.completed_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _build_to_domain(row)

    def update(self, build: IndexBuild) -> IndexBuild:
        with self._sf() as session:
            row = session.get(KnowledgeIndexBuildORM, build.id)
            if row is None:
                raise ValueError(f"Knowledge index build not found: {build.id}")
            row.status = build.status
            row.collection_name = build.collection_name
            row.chunk_count = build.chunk_count
            row.error = build.error
            row.metadata_json = dict(build.metadata or {})
            row.started_at = build.started_at
            row.completed_at = build.completed_at
            session.commit()
            session.refresh(row)
            return _build_to_domain(row)

    def get(self, build_id: str) -> IndexBuild | None:
        with self._sf() as session:
            row = session.get(KnowledgeIndexBuildORM, build_id)
            return _build_to_domain(row) if row else None

    def list_for_corpus(self, corpus_uuid: str) -> list[IndexBuild]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIndexBuildORM)
                .where(KnowledgeIndexBuildORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeIndexBuildORM.created_at.desc())
            ).scalars().all()
            return [_build_to_domain(row) for row in rows]

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeIndexBuildORM).where(KnowledgeIndexBuildORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyQueryRunStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def get(self, query_run_id: str) -> QueryRun | None:
        with self._sf() as session:
            row = session.get(KnowledgeQueryRunORM, query_run_id)
            return _query_run_to_domain(row) if row is not None else None

    def save(self, run: QueryRun) -> QueryRun:
        with self._sf() as session:
            row = KnowledgeQueryRunORM(
                id=run.id,
                query_text=run.query,
                corpus_uuid=run.corpus_uuid,
                build_ids=list(run.build_ids),
                retrieval_profile_key=run.retrieval_profile_key,
                context_profile_key=run.context_profile_key,
                latency_ms=run.latency_ms,
                result_count=run.result_count,
                citations=[
                    {
                        "source_id": item.source_id,
                        "build_id": item.build_id,
                        "snippet": item.snippet,
                        "score": item.score,
                        "title": item.title,
                        "chunk_id": item.chunk_id,
                        "metadata": dict(item.metadata or {}),
                    }
                    for item in run.citations
                ],
                context_text=run.context_text,
                feedback=run.feedback,
                compare_mode=run.compare_mode,
                metadata_json=dict(run.metadata or {}),
                created_at=run.created_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _query_run_to_domain(row)

    def list_recent(self, *, corpus_uuid: str | None = None, limit: int = 20) -> list[QueryRun]:
        with self._sf() as session:
            stmt = select(KnowledgeQueryRunORM).order_by(KnowledgeQueryRunORM.created_at.desc()).limit(limit)
            if corpus_uuid:
                stmt = stmt.where(KnowledgeQueryRunORM.corpus_uuid == corpus_uuid)
            rows = session.execute(stmt).scalars().all()
            return [_query_run_to_domain(row) for row in rows]

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeQueryRunORM).where(KnowledgeQueryRunORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


__all__ = [
    "SQLAlchemyIndexBuildStore",
    "SQLAlchemyQueryRunStore",
    "SQLAlchemySourceStore",
]
