from __future__ import annotations

# backend/apps/kb/kb_reading/storage/upload_reader.py
# Feladat: Feltöltött fájl tartalom beolvasása.
# Sárközi Mihály - 2026.06.07

from typing import Protocol

from apps.kb.shared.errors import KbValidationError

READ_CHUNK_BYTES = 1024 * 1024


class ReadableUpload(Protocol):
    """Feltöltött fájl olvasható felülete a becsléshez."""
    filename: str | None
    content_type: str | None

    """Beolvassa a feltöltött tartalom egy részét vagy egészét."""
    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_limited(upload: ReadableUpload, *, max_bytes: int) -> bytes:
    """Korlátozott méretű feltöltött tartalmat olvas be."""
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise KbValidationError(f"File too large (max {max_bytes // (1024 * 1024)} MB).")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise KbValidationError("Uploaded file is empty.")
    return raw


__all__ = ["READ_CHUNK_BYTES", "ReadableUpload", "read_upload_limited"]
