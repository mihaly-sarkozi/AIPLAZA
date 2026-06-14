from __future__ import annotations

from sqlalchemy import delete, func, select

from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship


class RelationshipRepository:
    _ENTITY_TYPES = frozenset({"entity"})
    _TOPIC_TYPES = frozenset({"topic"})
    _TEMPORAL_TYPES = frozenset({"time"})
    _SPATIAL_TYPES = frozenset({"location"})
    _PROCESS_TYPES = frozenset({"process"})

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, relationships: list[KnowledgeRelationship]) -> int:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id))
            for relationship in relationships:
                session.add(relationship)
            session.commit()
            return len(relationships)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return int(
                session.execute(
                    select(func.count(KnowledgeRelationship.id)).where(
                        KnowledgeRelationship.job_id == job_id
                    )
                ).scalar()
                or 0
            )

    def count_relationship_groups_for_job(self, job_id: str) -> dict[str, int]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id)
                ).scalars()
            )
        counts = {"entity": 0, "topic": 0, "time": 0, "location": 0, "process": 0}
        for row in rows:
            if row.from_type in self._ENTITY_TYPES or row.to_type in self._ENTITY_TYPES:
                counts["entity"] += 1
            if row.from_type in self._TOPIC_TYPES or row.relation == "has_topic":
                counts["topic"] += 1
            if row.from_type in self._TEMPORAL_TYPES or row.to_type in self._TEMPORAL_TYPES:
                counts["time"] += 1
            if row.from_type in self._SPATIAL_TYPES or row.to_type in self._SPATIAL_TYPES:
                counts["location"] += 1
            if (
                row.from_type in self._PROCESS_TYPES
                or row.to_type in self._PROCESS_TYPES
                or row.relation in {"has_step", "responsible_for"}
            ):
                counts["process"] += 1
        return counts

    def list_for_job(self, job_id: str) -> list[KnowledgeRelationship]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id)
                ).scalars()
            )

    def list_for_chunks(self, job_id: str, chunk_ids: list[str]) -> list[KnowledgeRelationship]:
        if not chunk_ids:
            return []
        chunk_id_set = set(chunk_ids)
        return [
            row
            for row in self.list_for_job(job_id)
            if row.to_type == "chunk" and row.to_id in chunk_id_set
            or row.from_type == "chunk" and row.from_id in chunk_id_set
            or any(chunk_id in chunk_id_set for chunk_id in (row.evidence_chunk_ids or []))
        ]


__all__ = ["RelationshipRepository"]
