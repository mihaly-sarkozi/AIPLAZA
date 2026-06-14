from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent
from apps.kb.kb_understanding.orm.NormalizedContentPart import NormalizedContentPart


class ContentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def begin_extract(self, training_item_id: str, content: ExtractedContent) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(ExtractedContentPart).where(
                    ExtractedContentPart.training_item_id == training_item_id
                )
            )
            session.execute(
                delete(ExtractedContent).where(ExtractedContent.training_item_id == training_item_id)
            )
            session.add(content)
            session.commit()

    def bulk_insert_parts(self, parts: list[ExtractedContentPart]) -> None:
        if not parts:
            return
        with self._session_factory() as session:
            session.add_all(parts)
            session.commit()

    def finalize_extract(self, extracted_content_id: str, *, patch: dict) -> None:
        with self._session_factory() as session:
            row = session.get(ExtractedContent, extracted_content_id)
            if row is None:
                return
            for key, value in patch.items():
                if key == "metadata_json":
                    metadata = dict(row.metadata_json or {})
                    metadata.update(value)
                    row.metadata_json = metadata
                elif hasattr(row, key):
                    setattr(row, key, value)
            session.commit()

    def replace_extracted_with_parts(
        self,
        training_item_id: str,
        content: ExtractedContent,
        parts: list[ExtractedContentPart],
        *,
        batch_size: int = 50,
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(ExtractedContentPart).where(
                    ExtractedContentPart.training_item_id == training_item_id
                )
            )
            session.execute(
                delete(ExtractedContent).where(ExtractedContent.training_item_id == training_item_id)
            )
            session.add(content)
            session.flush()
            for index in range(0, len(parts), batch_size):
                session.add_all(parts[index : index + batch_size])
                session.flush()
            session.commit()

    def delete_normalized_by_training_item(self, training_item_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(NormalizedContentPart).where(
                    NormalizedContentPart.training_item_id == training_item_id
                )
            )
            session.execute(
                delete(NormalizedContent).where(NormalizedContent.training_item_id == training_item_id)
            )
            session.commit()

    def create_normalized_summary(self, content: NormalizedContent) -> None:
        with self._session_factory() as session:
            session.add(content)
            session.commit()

    def bulk_insert_normalized_parts(self, parts: list[NormalizedContentPart]) -> None:
        if not parts:
            return
        with self._session_factory() as session:
            session.add_all(parts)
            session.commit()

    def finalize_normalized_summary(self, normalized_content_id: str, *, patch: dict) -> None:
        with self._session_factory() as session:
            row = session.get(NormalizedContent, normalized_content_id)
            if row is None:
                return
            for key, value in patch.items():
                if key == "metadata_json":
                    metadata = dict(row.metadata_json or {})
                    metadata.update(value)
                    row.metadata_json = metadata
                elif hasattr(row, key):
                    setattr(row, key, value)
            session.commit()

    def iter_normalizable_extracted_parts(
        self,
        training_item_id: str,
        *,
        batch_size: int = 100,
        part_types: set[str] | None = None,
    ) -> Iterator[list[ExtractedContentPart]]:
        usable = part_types or {part_type.value for part_type in NORMALIZABLE_PART_TYPES}
        offset = 0
        while True:
            with self._session_factory() as session:
                query = (
                    select(ExtractedContentPart)
                    .where(
                        ExtractedContentPart.training_item_id == training_item_id,
                        ExtractedContentPart.part_type.in_(sorted(usable)),
                        ExtractedContentPart.status == "completed",
                    )
                    .order_by(
                        ExtractedContentPart.part_index.asc(),
                        ExtractedContentPart.page_number.asc().nullsfirst(),
                    )
                    .offset(offset)
                    .limit(batch_size)
                )
                rows = list(session.execute(query).scalars().all())
                for row in rows:
                    session.expunge(row)
            if not rows:
                break
            yield rows
            offset += len(rows)

    def iter_normalized_parts_for_item(
        self,
        training_item_id: str,
        *,
        batch_size: int = 100,
    ) -> Iterator[list[NormalizedContentPart]]:
        offset = 0
        while True:
            with self._session_factory() as session:
                query = (
                    select(NormalizedContentPart)
                    .where(
                        NormalizedContentPart.training_item_id == training_item_id,
                        NormalizedContentPart.status == "completed",
                    )
                    .order_by(
                        NormalizedContentPart.document_order.asc().nullsfirst(),
                        NormalizedContentPart.page_number.asc().nullsfirst(),
                        NormalizedContentPart.part_index.asc(),
                    )
                    .offset(offset)
                    .limit(batch_size)
                )
                rows = list(session.execute(query).scalars().all())
                for row in rows:
                    session.expunge(row)
            if not rows:
                break
            yield rows
            offset += len(rows)

    def count_normalizable_extracted_parts(self, training_item_id: str) -> int:
        usable = {part_type.value for part_type in NORMALIZABLE_PART_TYPES}
        with self._session_factory() as session:
            count = session.execute(
                select(func.count())
                .select_from(ExtractedContentPart)
                .where(
                    ExtractedContentPart.training_item_id == training_item_id,
                    ExtractedContentPart.part_type.in_(sorted(usable)),
                    ExtractedContentPart.status == "completed",
                )
            ).scalar_one()
            return int(count or 0)

    def count_normalized_parts(self, training_item_id: str) -> int:
        with self._session_factory() as session:
            count = session.execute(
                select(func.count())
                .select_from(NormalizedContentPart)
                .where(
                    NormalizedContentPart.training_item_id == training_item_id,
                    NormalizedContentPart.status == "completed",
                    NormalizedContentPart.normalized_text.isnot(None),
                    NormalizedContentPart.normalized_text != "",
                )
            ).scalar_one()
            return int(count or 0)

    def get_extracted_for_item(self, training_item_id: str) -> ExtractedContent | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(ExtractedContent).where(ExtractedContent.training_item_id == training_item_id)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row

    def list_parts_for_item(
        self,
        training_item_id: str,
        *,
        part_types: set[str] | None = None,
        completed_only: bool = True,
    ) -> list[ExtractedContentPart]:
        with self._session_factory() as session:
            query = select(ExtractedContentPart).where(
                ExtractedContentPart.training_item_id == training_item_id
            )
            if part_types:
                query = query.where(ExtractedContentPart.part_type.in_(sorted(part_types)))
            if completed_only:
                query = query.where(ExtractedContentPart.status == "completed")
            query = query.order_by(
                ExtractedContentPart.page_number.asc().nullsfirst(),
                ExtractedContentPart.part_index.asc(),
            )
            rows = session.execute(query).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def list_normalized_parts_for_item(self, training_item_id: str) -> list[NormalizedContentPart]:
        with self._session_factory() as session:
            query = (
                select(NormalizedContentPart)
                .where(
                    NormalizedContentPart.training_item_id == training_item_id,
                    NormalizedContentPart.status == "completed",
                )
                .order_by(
                    NormalizedContentPart.document_order.asc().nullsfirst(),
                    NormalizedContentPart.page_number.asc().nullsfirst(),
                    NormalizedContentPart.part_index.asc(),
                )
            )
            rows = session.execute(query).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def count_usable_parts(self, training_item_id: str) -> int:
        usable = {part_type.value for part_type in NORMALIZABLE_PART_TYPES}
        with self._session_factory() as session:
            count = session.execute(
                select(func.count())
                .select_from(ExtractedContentPart)
                .where(
                    ExtractedContentPart.training_item_id == training_item_id,
                    ExtractedContentPart.part_type.in_(sorted(usable)),
                    ExtractedContentPart.status == "completed",
                    ExtractedContentPart.text.isnot(None),
                    ExtractedContentPart.text != "",
                )
            ).scalar_one()
            return int(count or 0)

    def get_normalized_for_item(self, training_item_id: str) -> NormalizedContent | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(NormalizedContent).where(NormalizedContent.training_item_id == training_item_id)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row


__all__ = ["ContentRepository"]
