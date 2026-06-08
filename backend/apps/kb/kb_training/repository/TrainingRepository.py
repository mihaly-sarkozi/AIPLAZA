from __future__ import annotations

# backend/apps/kb/kb_training/repository/TrainingRepository.py
# Feladat: Training batch / item / event SQLAlchemy perzisztencia (közvetlenül hívható).
# Sárközi Mihály - 2026.06.07

from sqlalchemy import select

from shared.utils.clock import utc_now

from apps.kb.kb_training.config import MetricsConf
from apps.kb.kb_training.dto.TrainingFileItemSave import TrainingFileItemSave
from apps.kb.kb_training.dto.TrainingFilesBatchSave import TrainingFilesBatchSave
from apps.kb.kb_training.dto.TrainingTextBatchSave import TrainingTextBatchSave
from apps.kb.kb_training.dto.TrainingTextSavedBatch import TrainingTextSavedBatch
from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_training.enums.TrainingMetric import TrainingMetric
from apps.kb.kb_training.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_training.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_training.orm.TrainingEvent import TrainingEvent
from apps.kb.kb_training.orm.TrainingItem import TrainingItem
from apps.kb.kb_training.enums.TrainingAuditEventType import TrainingAuditEventType
from apps.kb.shared.ids import new_id


class TrainingRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get_batch(self, batch_id: str) -> TrainingBatch | None:
        with self._session_factory() as session:
            return session.get(TrainingBatch, batch_id)

    def get_item(self, item_id: str) -> TrainingItem | None:
        with self._session_factory() as session:
            return session.get(TrainingItem, item_id)

    def list_items_for_batch(self, training_batch_id: str) -> list[TrainingItem]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(TrainingItem)
                    .where(TrainingItem.training_batch_id == training_batch_id)
                    .order_by(TrainingItem.created_at.asc(), TrainingItem.id.asc())
                ).scalars().all()
            )

    def list_events_for_batch(self, training_batch_id: str) -> list[TrainingEvent]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(TrainingEvent)
                    .where(TrainingEvent.training_batch_id == training_batch_id)
                    .order_by(TrainingEvent.created_at.asc(), TrainingEvent.id.asc())
                ).scalars().all()
            )

    def save_training_text_batch(self, save: TrainingTextBatchSave) -> TrainingTextSavedBatch:
        now = utc_now()
        batch = TrainingBatch(
            id=save.batch_id,
            tenant=save.tenant,
            knowledge_base_id=save.knowledge_base_id,
            input_channel="text",
            status=TrainingBatchStatus.COMPLETED.value,
            batch_size=1,
            queued_count=1,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=save.created_by,
            created_at=now,
            completed_at=now,
            metadata_json={"input_types": ["text"]},
        )
        MetricsConf.increment(TrainingMetric.BATCH_CREATED, input_channel=batch.input_channel)
        
        item = TrainingItem(
            id=save.item_id,
            training_batch_id=save.batch_id,
            knowledge_base_id=save.knowledge_base_id,
            input_type="text",
            title=save.title,
            status=TrainingItemStatus.ACCEPTED.value,
            raw_ref=save.raw_ref,
            content_hash=save.content_hash,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
            mime_type=save.mime_type,
            size_bytes=save.size_bytes,
            metadata_json=dict(save.metadata),
            created_at=now,
            updated_at=now,
        )
        MetricsConf.increment(TrainingMetric.ITEM_ACCEPTED, input_type=item.input_type)
    
        events = [
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_CREATED.value,
                message="",
                details_json={"batch_size": 1, "input_channel": "text"},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=save.item_id,
                event_type=TrainingAuditEventType.TRAINING_ITEM_ACCEPTED.value,
                message="",
                details_json={"raw_ref": save.raw_ref},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_COMPLETED.value,
                message="",
                details_json={
                    "status": TrainingBatchStatus.COMPLETED.value,
                    "accepted_count": 1,
                },
                created_at=now,
            ),
        ]
        with self._session_factory() as session:
            session.add(batch)
            session.add(item)
            for event in events:
                session.add(event)
            session.commit()

        MetricsConf.increment(
            TrainingMetric.BATCH_COMPLETED,
            status=TrainingBatchStatus.COMPLETED.value,
        )
        return TrainingTextSavedBatch(
            batch_id=save.batch_id,
            item_id=save.item_id,
            created_at=now,
            completed_at=batch.completed_at,
        )

    def save_training_files_batch(self, save: TrainingFilesBatchSave) -> TrainingTextSavedBatch:
        if not save.items:
            raise ValueError("Training files batch requires at least one item.")
        now = utc_now()
        batch_size = len(save.items)
        batch = TrainingBatch(
            id=save.batch_id,
            tenant=save.tenant,
            knowledge_base_id=save.knowledge_base_id,
            input_channel="file",
            status=TrainingBatchStatus.COMPLETED.value,
            batch_size=batch_size,
            queued_count=batch_size,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=save.created_by,
            created_at=now,
            completed_at=now,
            metadata_json={"input_types": ["file"]},
        )
        MetricsConf.increment(TrainingMetric.BATCH_CREATED, input_channel=batch.input_channel)

        orm_items: list[TrainingItem] = []
        for item_save in save.items:
            orm_items.append(self._build_training_item(item_save, batch_id=save.batch_id, kb_id=save.knowledge_base_id, now=now))
            MetricsConf.increment(TrainingMetric.ITEM_ACCEPTED, input_type="file")

        events = [
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_CREATED.value,
                message="",
                details_json={"batch_size": batch_size, "input_channel": "file"},
                created_at=now,
            ),
            *[
                TrainingEvent(
                    id=new_id("training_event"),
                    training_batch_id=save.batch_id,
                    training_item_id=item.id,
                    event_type=TrainingAuditEventType.TRAINING_ITEM_ACCEPTED.value,
                    message="",
                    details_json={"raw_ref": item.raw_ref},
                    created_at=now,
                )
                for item in orm_items
            ],
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_COMPLETED.value,
                message="",
                details_json={
                    "status": TrainingBatchStatus.COMPLETED.value,
                    "accepted_count": batch_size,
                },
                created_at=now,
            ),
        ]
        with self._session_factory() as session:
            session.add(batch)
            for item in orm_items:
                session.add(item)
            for event in events:
                session.add(event)
            session.commit()

        MetricsConf.increment(TrainingMetric.BATCH_COMPLETED, status=TrainingBatchStatus.COMPLETED.value)
        first_item = save.items[0]
        return TrainingTextSavedBatch(
            batch_id=save.batch_id,
            item_id=first_item.item_id,
            created_at=now,
            completed_at=batch.completed_at,
        )

    @staticmethod
    def _build_training_item(
        item_save: TrainingFileItemSave,
        *,
        batch_id: str,
        kb_id: str,
        now,
        input_type: str = "file",
    ) -> TrainingItem:
        return TrainingItem(
            id=item_save.item_id,
            training_batch_id=batch_id,
            knowledge_base_id=kb_id,
            input_type=input_type,
            title=item_save.title,
            status=TrainingItemStatus.ACCEPTED.value,
            raw_ref=item_save.raw_ref,
            content_hash=item_save.content_hash,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
            mime_type=item_save.mime_type,
            size_bytes=item_save.size_bytes,
            metadata_json=dict(item_save.metadata),
            created_at=now,
            updated_at=now,
        )

    def find_duplicate_by_content_hash(
        self,
        knowledge_base_id: str,
        content_hash: str,
    ) -> TrainingItem | None:
        digest = str(content_hash or "").strip()
        if not digest:
            return None
        with self._session_factory() as session:
            return session.execute(
                select(TrainingItem)
                .where(
                    TrainingItem.knowledge_base_id == knowledge_base_id,
                    TrainingItem.content_hash == digest,
                    TrainingItem.status == TrainingItemStatus.ACCEPTED.value,
                )
                .order_by(TrainingItem.created_at.desc(), TrainingItem.id.desc())
                .limit(1)
            ).scalar_one_or_none()


__all__ = ["TrainingRepository"]
