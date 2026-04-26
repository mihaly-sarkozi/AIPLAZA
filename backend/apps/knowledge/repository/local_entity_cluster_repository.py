from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.repository.models.local_entity_cluster_orm import KnowledgeLocalEntityClusterORM


def _parse_run_id(run_id: str | UUID) -> UUID:
    return run_id if isinstance(run_id, UUID) else UUID(str(run_id))


def _parse_source_id(source_id: str | UUID) -> UUID:
    return source_id if isinstance(source_id, UUID) else UUID(str(source_id))


def _dt_to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _dt_from_row(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _uuid_list_for_json(ids: list[UUID]) -> list[str]:
    return [str(item) for item in ids]


def _uuid_list_from_json(raw: Any) -> list[UUID]:
    if not raw:
        return []
    return [UUID(str(item)) for item in raw]


def _cluster_to_row(cluster: LocalEntityCluster) -> KnowledgeLocalEntityClusterORM:
    return KnowledgeLocalEntityClusterORM(
        local_entity_id=cluster.local_entity_id,
        run_id=cluster.run_id,
        source_id=cluster.source_id,
        canonical_name=cluster.canonical_name or "",
        entity_type=cluster.entity_type,
        normalized_key=cluster.normalized_key or "",
        mention_ids=_uuid_list_for_json(cluster.mention_ids),
        claim_ids=_uuid_list_for_json(cluster.claim_ids),
        sentence_ids=_uuid_list_for_json(cluster.sentence_ids),
        surface_forms=list(cluster.surface_forms),
        evidence_refs=list(cluster.evidence_refs),
        confidence=float(cluster.confidence),
        coherence_score=float(cluster.coherence_score),
        resolver_version=cluster.resolver_version,
        explanation_json=dict(cluster.explanation or {}),
        created_at=_dt_to_naive_utc(cluster.created_at),
    )


def _row_to_cluster(row: KnowledgeLocalEntityClusterORM) -> LocalEntityCluster:
    return LocalEntityCluster(
        local_entity_id=row.local_entity_id,
        run_id=row.run_id,
        source_id=row.source_id,
        canonical_name=row.canonical_name or "",
        entity_type=row.entity_type,
        normalized_key=row.normalized_key or "",
        mention_ids=_uuid_list_from_json(row.mention_ids),
        claim_ids=_uuid_list_from_json(row.claim_ids),
        sentence_ids=_uuid_list_from_json(row.sentence_ids),
        surface_forms=list(row.surface_forms or []),
        evidence_refs=list(row.evidence_refs or []),
        confidence=float(row.confidence or 0.0),
        coherence_score=float(row.coherence_score or 0.0),
        resolver_version=row.resolver_version or "local_resolver_v1",
        created_at=_dt_from_row(row.created_at),
        explanation=dict(getattr(row, "explanation_json", None) or {}),
    )


class LocalEntityClusterRepository:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def save(self, cluster: LocalEntityCluster) -> LocalEntityCluster:
        row = _cluster_to_row(cluster)
        with self._sf() as session:
            merged = session.merge(row)
            session.commit()
            session.refresh(merged)
            return _row_to_cluster(merged)

    def save_many(self, clusters: list[LocalEntityCluster]) -> list[LocalEntityCluster]:
        if not clusters:
            return []
        with self._sf() as session:
            merged_rows = [session.merge(_cluster_to_row(item)) for item in clusters]
            session.commit()
            for row in merged_rows:
                session.refresh(row)
            return [_row_to_cluster(row) for row in merged_rows]

    def list_by_run(self, run_id: str | UUID) -> list[LocalEntityCluster]:
        rid = _parse_run_id(run_id)
        with self._sf() as session:
            stmt = (
                select(KnowledgeLocalEntityClusterORM)
                .where(KnowledgeLocalEntityClusterORM.run_id == rid)
                .order_by(KnowledgeLocalEntityClusterORM.created_at.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_row_to_cluster(row) for row in rows]

    def list_by_source(self, source_id: str | UUID) -> list[LocalEntityCluster]:
        sid = _parse_source_id(source_id)
        with self._sf() as session:
            stmt = (
                select(KnowledgeLocalEntityClusterORM)
                .where(KnowledgeLocalEntityClusterORM.source_id == sid)
                .order_by(KnowledgeLocalEntityClusterORM.created_at.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_row_to_cluster(row) for row in rows]

    def delete_by_run(self, run_id: str | UUID) -> int:
        rid = _parse_run_id(run_id)
        with self._sf() as session:
            result = session.execute(delete(KnowledgeLocalEntityClusterORM).where(KnowledgeLocalEntityClusterORM.run_id == rid))
            session.commit()
            return int(result.rowcount or 0)

    def delete_by_source(self, source_id: str | UUID) -> int:
        sid = _parse_source_id(source_id)
        with self._sf() as session:
            result = session.execute(delete(KnowledgeLocalEntityClusterORM).where(KnowledgeLocalEntityClusterORM.source_id == sid))
            session.commit()
            return int(result.rowcount or 0)


__all__ = ["LocalEntityClusterRepository"]
