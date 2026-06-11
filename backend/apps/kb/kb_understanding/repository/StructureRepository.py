from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/StructureRepository.py
# Feladat: Strukturált blokkok perzisztencia, item-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_understanding.orm.StructuredBlock import StructuredBlock


class StructureRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_item(self, training_item_id: str, blocks: list[StructuredBlock]) -> int:
        with self._session_factory() as session:
            session.execute(
                delete(StructuredBlock).where(StructuredBlock.training_item_id == training_item_id)
            )
            for block in blocks:
                session.add(block)
            session.commit()
            return len(blocks)

    def list_for_item(self, training_item_id: str) -> list[StructuredBlock]:
        with self._session_factory() as session:
            blocks = list(
                session.execute(
                    select(StructuredBlock)
                    .where(StructuredBlock.training_item_id == training_item_id)
                    .order_by(StructuredBlock.order_index.asc())
                )
                .scalars()
                .all()
            )
            for block in blocks:
                session.expunge(block)
            return blocks


__all__ = ["StructureRepository"]
