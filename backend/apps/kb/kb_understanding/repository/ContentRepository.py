from __future__ import annotations

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent


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
