from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/ContentRepository.py
# Feladat: Kinyert és normalizált tartalom perzisztencia, item-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent


class ContentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_extracted(self, training_item_id: str, content: ExtractedContent) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(ExtractedContent).where(ExtractedContent.training_item_id == training_item_id)
            )
            session.add(content)
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
