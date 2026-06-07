from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_reading.domain.ReadEvent import ReadEvent
from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadItemStatus import ReadItemStatus
from apps.kb.kb_reading.domain.ReadRun import ReadRun
from apps.kb.kb_reading.mapper.reading_mapper import (
    apply_item_to_orm,
    apply_run_to_orm,
    read_event_to_domain,
    read_event_to_orm,
    read_item_to_domain,
    read_item_to_orm,
    read_run_to_domain,
    read_run_to_orm,
)
from apps.kb.kb_reading.orm.ReadingBatch import ReadingBatch
from apps.kb.kb_reading.orm.ReadingEvent import ReadingEvent
from apps.kb.kb_reading.orm.ReadingItem import ReadingItem


class ReadingRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_run(self, run: ReadRun) -> ReadRun:
        with self._session_factory() as session:
            row = read_run_to_orm(run)
            session.add(row)
            session.commit()
            session.refresh(row)
            return read_run_to_domain(row)

    def update_run(self, run: ReadRun) -> ReadRun:
        with self._session_factory() as session:
            row = session.get(ReadingBatch, run.id)
            if row is None:
                raise ValueError(f"Read run not found: {run.id}")
            apply_run_to_orm(run, row)
            session.commit()
            session.refresh(row)
            return read_run_to_domain(row)

    def get_run(self, run_id: str) -> ReadRun | None:
        with self._session_factory() as session:
            row = session.get(ReadingBatch, run_id)
            return read_run_to_domain(row) if row is not None else None

    def list_runs_for_kb(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReadRun]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ReadingBatch)
                .where(ReadingBatch.knowledge_base_id == knowledge_base_id)
                .order_by(ReadingBatch.created_at.desc(), ReadingBatch.id.desc())
                .offset(max(0, offset))
                .limit(max(1, limit))
            ).scalars().all()
            return [read_run_to_domain(row) for row in rows]

    def create_item(self, item: ReadItem) -> ReadItem:
        with self._session_factory() as session:
            row = read_item_to_orm(item)
            session.add(row)
            session.commit()
            session.refresh(row)
            return read_item_to_domain(row)

    def update_item(self, item: ReadItem) -> ReadItem:
        with self._session_factory() as session:
            row = session.get(ReadingItem, item.id)
            if row is None:
                raise ValueError(f"Read item not found: {item.id}")
            apply_item_to_orm(item, row)
            session.commit()
            session.refresh(row)
            return read_item_to_domain(row)

    def get_item(self, item_id: str) -> ReadItem | None:
        with self._session_factory() as session:
            row = session.get(ReadingItem, item_id)
            return read_item_to_domain(row) if row is not None else None

    def list_items_for_run(self, read_run_id: str) -> list[ReadItem]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ReadingItem)
                .where(ReadingItem.reading_batch_id == read_run_id)
                .order_by(ReadingItem.created_at.asc(), ReadingItem.id.asc())
            ).scalars().all()
            return [read_item_to_domain(row) for row in rows]

    def create_event(self, event: ReadEvent) -> ReadEvent:
        with self._session_factory() as session:
            row = read_event_to_orm(event)
            session.add(row)
            session.commit()
            session.refresh(row)
            return read_event_to_domain(row)

    def list_events_for_run(self, read_run_id: str) -> list[ReadEvent]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ReadingEvent)
                .where(ReadingEvent.reading_batch_id == read_run_id)
                .order_by(ReadingEvent.created_at.asc(), ReadingEvent.id.asc())
            ).scalars().all()
            return [read_event_to_domain(row) for row in rows]

    def find_duplicate_by_idempotency_key(
        self,
        knowledge_base_id: str,
        idempotency_key: str,
    ) -> ReadItem | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        with self._session_factory() as session:
            row = session.execute(
                select(ReadingItem)
                .where(
                    ReadingItem.knowledge_base_id == knowledge_base_id,
                    ReadingItem.idempotency_key == key,
                    ReadingItem.status == ReadItemStatus.ACCEPTED.value,
                )
                .order_by(ReadingItem.created_at.desc(), ReadingItem.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            return read_item_to_domain(row) if row is not None else None

    def find_latest_url_item(
        self,
        knowledge_base_id: str,
        origin_url: str,
    ) -> ReadItem | None:
        normalized_url = str(origin_url or "").strip()
        if not normalized_url:
            return None
        with self._session_factory() as session:
            row = session.execute(
                select(ReadingItem)
                .where(
                    ReadingItem.knowledge_base_id == knowledge_base_id,
                    ReadingItem.input_type == "url",
                    ReadingItem.origin_url == normalized_url,
                )
                .order_by(ReadingItem.created_at.desc(), ReadingItem.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            return read_item_to_domain(row) if row is not None else None


__all__ = ["ReadingRepository"]
