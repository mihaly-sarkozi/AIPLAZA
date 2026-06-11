from __future__ import annotations

# backend/apps/kb/kb_ingest/security/ArchiveGuard.py
# Feladat: Tömörített csomag méret- és mélység ellenőrzés.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

import io
from typing import Any
from zipfile import BadZipFile, ZipFile
from core.kernel.config.config_loader import settings
from apps.kb.kb_ingest.security.ReadingArchiveError import ReadingArchiveError
class ArchiveGuard:
    """Tömörített csomag méret és mélység ellenőrző."""
    def inspect_docx_bytes_or_raise(self, raw: bytes) -> dict[str, Any]:
        """Ellenőrzi a dokumentum csomagot vagy hibát dob."""
        max_entries = max(1, int(getattr(settings, "upload_docx_max_zip_entries", 5000) or 5000))
        max_decompressed = max(
            1,
            int(getattr(settings, "upload_docx_max_decompressed_bytes", 30 * 1024 * 1024) or (30 * 1024 * 1024)),
        )
        max_ratio = float(getattr(settings, "upload_docx_max_compression_ratio", 120.0) or 120.0)
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                return self._inspect_zip_or_raise(
                    archive,
                    max_entries=max_entries,
                    max_decompressed=max_decompressed,
                    max_ratio=max_ratio,
                )
        except BadZipFile as exc:
            raise ReadingArchiveError("Invalid DOCX archive.") from exc

    def _inspect_zip_or_raise(
        self,
        archive: ZipFile,
        *,
        max_entries: int,
        max_decompressed: int,
        max_ratio: float,
    ) -> dict[str, Any]:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        infos = archive.infolist()
        if len(infos) > max_entries:
            raise ReadingArchiveError("DOCX archive too complex (too many entries).")
        total_uncompressed = 0
        total_compressed = 0
        has_word_document = False
        has_content_types = False
        for info in infos:
            total_uncompressed += int(info.file_size or 0)
            total_compressed += int(info.compress_size or 0)
            member_name = str(info.filename or "")
            if member_name == "[Content_Types].xml":
                has_content_types = True
            if member_name == "word/document.xml":
                has_word_document = True
            if total_uncompressed > max_decompressed:
                raise ReadingArchiveError("DOCX uncompressed size exceeds allowed limit.")
        compressed_baseline = max(1, total_compressed)
        ratio = float(total_uncompressed) / float(compressed_baseline)
        if ratio > max_ratio:
            raise ReadingArchiveError("DOCX compression ratio is suspiciously high.")
        if not (has_word_document and has_content_types):
            raise ReadingArchiveError("DOCX archive structure invalid.")
        return {
            "entries": len(infos),
            "total_uncompressed": total_uncompressed,
            "total_compressed": total_compressed,
            "ratio": ratio,
        }
__all__ = ["ArchiveGuard"]
