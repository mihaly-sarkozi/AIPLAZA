from __future__ import annotations

from sqlalchemy import func, select

from apps.kb.kb_processing.orm.ProcessingEvent import ProcessingEvent
from apps.kb.shared.ids import new_id


class ProcessingEventRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def add_event(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str,
        event_type: str,
        status: str,
        message: str | None = None,
        duration_ms: int | None = None,
        input_summary_json: dict | None = None,
        output_summary_json: dict | None = None,
        metadata_json: dict | None = None,
        created_by: int | None = None,
    ) -> str:
        event = ProcessingEvent(
            id=new_id("proc_evt"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=event_type,
            status=status,
            message=(message or "")[:4000] or None,
            duration_ms=duration_ms,
            input_summary_json=dict(input_summary_json or {}),
            output_summary_json=dict(output_summary_json or {}),
            metadata_json=dict(metadata_json or {}),
            created_by=created_by,
        )
        with self._session_factory() as session:
            session.add(event)
            session.commit()
            return event.id

    def list_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        training_item_id: str | None = None,
        job_id: str | None = None,
        module: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProcessingEvent]:
        with self._session_factory() as session:
            query = (
                select(ProcessingEvent)
                .where(ProcessingEvent.knowledge_base_id == knowledge_base_id)
                .order_by(ProcessingEvent.created_at.desc(), ProcessingEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
            if training_item_id:
                query = query.where(ProcessingEvent.training_item_id == training_item_id)
            if job_id:
                query = query.where(ProcessingEvent.job_id == job_id)
            if module:
                query = query.where(ProcessingEvent.module == module)
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    def count_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        training_item_id: str | None = None,
        job_id: str | None = None,
        module: str | None = None,
    ) -> int:
        with self._session_factory() as session:
            query = (
                select(func.count())
                .select_from(ProcessingEvent)
                .where(ProcessingEvent.knowledge_base_id == knowledge_base_id)
            )
            if training_item_id:
                query = query.where(ProcessingEvent.training_item_id == training_item_id)
            if job_id:
                query = query.where(ProcessingEvent.job_id == job_id)
            if module:
                query = query.where(ProcessingEvent.module == module)
            return int(session.execute(query).scalar_one())

    def list_for_job(
        self,
        job_id: str,
        *,
        module: str | None = None,
        limit: int = 500,
    ) -> list[ProcessingEvent]:
        with self._session_factory() as session:
            query = (
                select(ProcessingEvent)
                .where(ProcessingEvent.job_id == job_id)
                .order_by(ProcessingEvent.created_at.asc(), ProcessingEvent.id.asc())
                .limit(limit)
            )
            if module:
                query = query.where(ProcessingEvent.module == module)
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["ProcessingEventRepository"]
