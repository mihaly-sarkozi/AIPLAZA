from __future__ import annotations

# backend/apps/kb/kb_reading/storage/ReadingStorage.py
# Feladat: Beolvasási nyers anyag tároló port (outbound) — az adapter ezt implementálja.
# Sárközi Mihály - 2026.06.07

from typing import BinaryIO, Protocol


class ReadingStorage(Protocol):
    """Nyers beolvasási tartalom perzisztálása előre felépített storage kulccsal."""

    def put_text(
        self,
        *,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> None: ...

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> None: ...

    def open_raw(self, key: str) -> BinaryIO: ...

    def delete_raw(self, key: str) -> None: ...


__all__ = ["ReadingStorage"]
