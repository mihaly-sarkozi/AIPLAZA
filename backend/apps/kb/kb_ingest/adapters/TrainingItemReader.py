from __future__ import annotations

# backend/apps/kb/kb_ingest/adapters/TrainingItemReader.py
# Feladat: Ingest item olvasási nézet a megértési pipeline számára — a kb_understanding
# IngestItemReaderInterface portját elégíti ki strukturálisan (shared contract DTO-val).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_ingest.orm.TrainingItem import TrainingItem
from apps.kb.shared.contracts import IngestItemSnapshot


class TrainingItemReader:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get_item_snapshot(self, item_id: str) -> IngestItemSnapshot | None:
        with self._session_factory() as session:
            item = session.get(TrainingItem, item_id)
            if item is None:
                return None
            return IngestItemSnapshot(
                item_id=item.id,
                training_batch_id=item.training_batch_id,
                knowledge_base_id=item.knowledge_base_id,
                status=item.status,
                raw_ref=item.raw_ref,
                mime_type=item.mime_type,
                input_type=item.input_type,
                original_filename=item.original_filename,
                title=item.title or "",
                content_hash=item.content_hash,
            )


__all__ = ["TrainingItemReader"]
