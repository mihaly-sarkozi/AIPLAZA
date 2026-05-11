from __future__ import annotations

from sqlalchemy import delete, func, select

from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.models import (
    KnowledgeIngestEventORM,
    KnowledgeIngestInputORM,
    KnowledgeIngestItemORM,
    KnowledgeIngestRunORM,
)


def _run_to_domain(row: KnowledgeIngestRunORM) -> IngestRun:
    return IngestRun(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        input_channel=row.input_channel,
        status=row.status,  # type: ignore[arg-type]
        batch_size=row.batch_size,
        queued_count=row.queued_count,
        processing_count=row.processing_count,
        completed_count=row.completed_count,
        failed_count=row.failed_count,
        duplicate_count=row.duplicate_count,
        rejected_count=row.rejected_count,
        continue_on_error=bool(row.continue_on_error),
        pipeline_route=row.pipeline_route,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_json or {}),
    )


def _item_to_domain(row: KnowledgeIngestItemORM) -> IngestItem:
    return IngestItem(
        id=row.id,
        ingest_run_id=row.ingest_run_id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        queue_order=row.queue_order,
        input_type=row.input_type,  # type: ignore[arg-type]
        display_name=row.display_name,
        title=row.title,
        origin=row.origin,
        status=row.status,  # type: ignore[arg-type]
        progress_message=row.progress_message,
        result_message=row.result_message,
        error_code=row.error_code,
        error_message=row.error_message,
        duplicate_of_item_id=row.duplicate_of_item_id,
        duplicate_of_source_id=row.duplicate_of_source_id,
        pipeline_route=row.pipeline_route,
        parser_job_id=row.parser_job_id,
        source_id=row.source_id,
        content_hash=row.content_hash,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_json or {}),
    )


def _input_to_domain(row: KnowledgeIngestInputORM) -> IngestInput:
    return IngestInput(
        id=row.id,
        ingest_item_id=row.ingest_item_id,
        tenant="",
        input_type=row.input_type,  # type: ignore[arg-type]
        storage_provider=row.storage_provider,
        bucket_name=row.bucket_name,
        object_key=row.object_key,
        original_filename=row.original_filename,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        text_content=row.text_content,
        origin_url=row.origin_url,
        external_ref=row.external_ref,
        checksum_sha256=row.checksum_sha256,
        encoding=row.encoding,
        language_hint=row.language_hint,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_json or {}),
    )


def _event_to_domain(row: KnowledgeIngestEventORM) -> IngestEvent:
    return IngestEvent(
        id=row.id,
        tenant="",
        ingest_run_id=row.ingest_run_id,
        ingest_item_id=row.ingest_item_id,
        event_type=row.event_type,
        status=row.status,
        message=row.message,
        details=dict(row.details_json or {}),
        created_at=row.created_at,
        created_by=row.created_by,
    )


class SQLAlchemyIngestRunStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, run: IngestRun) -> IngestRun:
        with self._sf() as session:
            row = KnowledgeIngestRunORM(
                id=run.id,
                corpus_uuid=run.corpus_uuid,
                input_channel=run.input_channel,
                status=run.status,
                batch_size=run.batch_size,
                queued_count=run.queued_count,
                processing_count=run.processing_count,
                completed_count=run.completed_count,
                failed_count=run.failed_count,
                duplicate_count=run.duplicate_count,
                rejected_count=run.rejected_count,
                continue_on_error=run.continue_on_error,
                pipeline_route=run.pipeline_route,
                metadata_json=dict(run.metadata or {}),
                created_at=run.created_at,
                updated_at=run.updated_at,
                created_by=run.created_by,
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _run_to_domain(row)

    def update(self, run: IngestRun) -> IngestRun:
        with self._sf() as session:
            row = session.get(KnowledgeIngestRunORM, run.id)
            if row is None:
                raise ValueError(f"Ingest run not found: {run.id}")
            row.status = run.status
            row.batch_size = run.batch_size
            row.queued_count = run.queued_count
            row.processing_count = run.processing_count
            row.completed_count = run.completed_count
            row.failed_count = run.failed_count
            row.duplicate_count = run.duplicate_count
            row.rejected_count = run.rejected_count
            row.pipeline_route = run.pipeline_route
            row.metadata_json = dict(run.metadata or {})
            row.started_at = run.started_at
            row.completed_at = run.completed_at
            row.updated_at = run.updated_at
            session.commit()
            session.refresh(row)
            return _run_to_domain(row)

    def get(self, run_id: str) -> IngestRun | None:
        with self._sf() as session:
            row = session.get(KnowledgeIngestRunORM, run_id)
            return _run_to_domain(row) if row else None

    def list_for_corpus(self, corpus_uuid: str, *, limit: int = 20, offset: int = 0) -> list[IngestRun]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestRunORM)
                .where(KnowledgeIngestRunORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeIngestRunORM.created_at.desc())
                .offset(max(0, offset))
                .limit(limit)
            ).scalars().all()
            return [_run_to_domain(row) for row in rows]

    def list_recent(self, *, limit: int = 20) -> list[IngestRun]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestRunORM)
                .order_by(KnowledgeIngestRunORM.created_at.desc())
                .limit(limit)
            ).scalars().all()
            return [_run_to_domain(row) for row in rows]

    def count_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            value = session.execute(
                select(func.count()).select_from(KnowledgeIngestRunORM).where(KnowledgeIngestRunORM.corpus_uuid == corpus_uuid)
            ).scalar_one()
            return int(value or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeIngestRunORM).where(KnowledgeIngestRunORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyIngestItemStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, items: list[IngestItem]) -> list[IngestItem]:
        if not items:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeIngestItemORM(
                    id=item.id,
                    ingest_run_id=item.ingest_run_id,
                    corpus_uuid=item.corpus_uuid,
                    queue_order=item.queue_order,
                    input_type=item.input_type,
                    display_name=item.display_name,
                    title=item.title,
                    origin=item.origin,
                    status=item.status,
                    progress_message=item.progress_message,
                    result_message=item.result_message,
                    error_code=item.error_code,
                    error_message=item.error_message,
                    duplicate_of_item_id=item.duplicate_of_item_id,
                    duplicate_of_source_id=item.duplicate_of_source_id,
                    pipeline_route=item.pipeline_route,
                    parser_job_id=item.parser_job_id,
                    source_id=item.source_id,
                    content_hash=item.content_hash,
                    metadata_json=dict(item.metadata or {}),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    created_by=item.created_by,
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                )
                for item in items
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_item_to_domain(row) for row in rows]

    def update(self, item: IngestItem) -> IngestItem:
        with self._sf() as session:
            row = session.get(KnowledgeIngestItemORM, item.id)
            if row is None:
                raise ValueError(f"Ingest item not found: {item.id}")
            row.status = item.status
            row.progress_message = item.progress_message
            row.result_message = item.result_message
            row.error_code = item.error_code
            row.error_message = item.error_message
            row.duplicate_of_item_id = item.duplicate_of_item_id
            row.duplicate_of_source_id = item.duplicate_of_source_id
            row.pipeline_route = item.pipeline_route
            row.parser_job_id = item.parser_job_id
            row.source_id = item.source_id
            row.content_hash = item.content_hash
            row.metadata_json = dict(item.metadata or {})
            row.started_at = item.started_at
            row.completed_at = item.completed_at
            row.updated_at = item.updated_at
            session.commit()
            session.refresh(row)
            return _item_to_domain(row)

    def get(self, item_id: str) -> IngestItem | None:
        with self._sf() as session:
            row = session.get(KnowledgeIngestItemORM, item_id)
            return _item_to_domain(row) if row else None

    def list_for_run(self, run_id: str) -> list[IngestItem]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestItemORM)
                .where(KnowledgeIngestItemORM.ingest_run_id == run_id)
                .order_by(KnowledgeIngestItemORM.queue_order.asc(), KnowledgeIngestItemORM.created_at.asc())
            ).scalars().all()
            return [_item_to_domain(row) for row in rows]

    def list_for_corpus(self, corpus_uuid: str) -> list[IngestItem]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestItemORM)
                .where(KnowledgeIngestItemORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeIngestItemORM.created_at.desc())
            ).scalars().all()
            return [_item_to_domain(row) for row in rows]

    def find_by_hash(self, *, corpus_uuid: str, content_hash: str, exclude_item_id: str | None = None) -> IngestItem | None:
        with self._sf() as session:
            stmt = select(KnowledgeIngestItemORM).where(
                KnowledgeIngestItemORM.corpus_uuid == corpus_uuid,
                KnowledgeIngestItemORM.content_hash == content_hash,
            ).order_by(KnowledgeIngestItemORM.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                if exclude_item_id and row.id == exclude_item_id:
                    continue
                if row.status in {"completed", "duplicate"}:
                    return _item_to_domain(row)
            return None

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeIngestItemORM).where(KnowledgeIngestItemORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyIngestInputStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, inputs: list[IngestInput]) -> list[IngestInput]:
        if not inputs:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeIngestInputORM(
                    id=item.id,
                    ingest_item_id=item.ingest_item_id,
                    input_type=item.input_type,
                    storage_provider=item.storage_provider,
                    bucket_name=item.bucket_name,
                    object_key=item.object_key,
                    original_filename=item.original_filename,
                    mime_type=item.mime_type,
                    size_bytes=item.size_bytes,
                    text_content=item.text_content,
                    origin_url=item.origin_url,
                    external_ref=item.external_ref,
                    checksum_sha256=item.checksum_sha256,
                    encoding=item.encoding,
                    language_hint=item.language_hint,
                    metadata_json=dict(item.metadata or {}),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in inputs
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_input_to_domain(row) for row in rows]

    def get_for_item(self, item_id: str) -> IngestInput | None:
        with self._sf() as session:
            row = session.execute(
                select(KnowledgeIngestInputORM).where(KnowledgeIngestInputORM.ingest_item_id == item_id)
            ).scalar_one_or_none()
            return _input_to_domain(row) if row else None

    def list_file_objects_for_corpus(self, corpus_uuid: str) -> list[tuple[str, str]]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestInputORM.bucket_name, KnowledgeIngestInputORM.object_key)
                .join(KnowledgeIngestItemORM, KnowledgeIngestItemORM.id == KnowledgeIngestInputORM.ingest_item_id)
                .where(
                    KnowledgeIngestItemORM.corpus_uuid == corpus_uuid,
                    KnowledgeIngestInputORM.input_type == "file",
                    KnowledgeIngestInputORM.bucket_name.is_not(None),
                    KnowledgeIngestInputORM.object_key.is_not(None),
                )
            ).all()
            return [
                (str(bucket_name), str(object_key))
                for bucket_name, object_key in rows
                if str(bucket_name or "").strip() and str(object_key or "").strip()
            ]

    def uploaded_file_size_bytes_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            value = session.execute(
                select(func.coalesce(func.sum(KnowledgeIngestInputORM.size_bytes), 0))
                .join(KnowledgeIngestItemORM, KnowledgeIngestItemORM.id == KnowledgeIngestInputORM.ingest_item_id)
                .where(
                    KnowledgeIngestItemORM.corpus_uuid == corpus_uuid,
                    KnowledgeIngestInputORM.input_type == "file",
                )
            ).scalar_one()
            return max(0, int(value or 0))

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            item_ids = select(KnowledgeIngestItemORM.id).where(KnowledgeIngestItemORM.corpus_uuid == corpus_uuid)
            result = session.execute(delete(KnowledgeIngestInputORM).where(KnowledgeIngestInputORM.ingest_item_id.in_(item_ids)))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyIngestEventStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, event: IngestEvent) -> IngestEvent:
        with self._sf() as session:
            row = KnowledgeIngestEventORM(
                id=event.id,
                ingest_run_id=event.ingest_run_id,
                ingest_item_id=event.ingest_item_id,
                event_type=event.event_type,
                status=event.status,
                message=event.message,
                details_json=dict(event.details or {}),
                created_at=event.created_at,
                created_by=event.created_by,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _event_to_domain(row)

    def list_for_run(self, run_id: str) -> list[IngestEvent]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeIngestEventORM)
                .where(KnowledgeIngestEventORM.ingest_run_id == run_id)
                .order_by(KnowledgeIngestEventORM.created_at.asc())
            ).scalars().all()
            return [_event_to_domain(row) for row in rows]

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            run_ids = select(KnowledgeIngestRunORM.id).where(KnowledgeIngestRunORM.corpus_uuid == corpus_uuid)
            result = session.execute(delete(KnowledgeIngestEventORM).where(KnowledgeIngestEventORM.ingest_run_id.in_(run_ids)))
            session.commit()
            return int(result.rowcount or 0)


__all__ = [
    "SQLAlchemyIngestEventStore",
    "SQLAlchemyIngestInputStore",
    "SQLAlchemyIngestItemStore",
    "SQLAlchemyIngestRunStore",
]
