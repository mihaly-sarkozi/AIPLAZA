from __future__ import annotations

# backend/apps/kb/kb_reading/service/ReadItemRawService.py
# Feladat: Beolvasási elem nyers tartalmának lekérése storage-ból.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_reading.dto.ReadItemRawContent import ReadItemRawContent
from apps.kb.kb_reading.ports.ReadingRepository import ReadingRepository
from apps.kb.kb_reading.service.ReadingResponseMapper import (
    find_item_by_id,
    resolve_filename,
    resolve_media_type,
)
from apps.kb.kb_reading.storage.RawReader import RawReader
from apps.kb.shared.errors import KbNotFoundError


class ReadItemRawService:
    """Nyers tartalom letöltése egy beolvasási elemhez."""

    def __init__(
        self,
        *,
        repository: ReadingRepository,
        raw_reader: RawReader,
    ) -> None:
        self._repository = repository
        self._raw_reader = raw_reader

    def get_raw(self, item_id: str) -> ReadItemRawContent:
        """Lekéri az elem nyers tartalmát."""
        item = find_item_by_id(self._repository, item_id)
        if item is None:
            raise KbNotFoundError("Read item not found.")
        if not item.raw_ref:
            raise KbNotFoundError("Read item has no stored raw content.")
        body = self._raw_reader.read_bytes(item.raw_ref)
        media_type = resolve_media_type(item)
        filename = resolve_filename(item)
        return ReadItemRawContent(body=body, media_type=media_type, filename=filename)


__all__ = ["ReadItemRawService"]
