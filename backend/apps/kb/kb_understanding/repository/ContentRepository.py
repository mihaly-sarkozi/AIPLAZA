from __future__ import annotations

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent


class ContentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

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

    def replace_normalized(self, training_item_id: str, content: NormalizedContent) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(NormalizedContent).where(NormalizedContent.training_item_id == training_item_id)
            )
            session.add(content)
            session.commit()

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
    ) -> list[ExtractedContentPart]:
        with self._session_factory() as session:
            query = select(ExtractedContentPart).where(
                ExtractedContentPart.training_item_id == training_item_id
            )
            if part_types:
                query = query.where(ExtractedContentPart.part_type.in_(sorted(part_types)))
            query = query.order_by(
                ExtractedContentPart.page_number.asc().nullsfirst(),
                ExtractedContentPart.part_index.asc(),
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
