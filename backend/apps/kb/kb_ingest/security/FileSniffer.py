from __future__ import annotations

# backend/apps/kb/kb_ingest/security/FileSniffer.py
# Feladat: Fájl típus felismerés a fejléc bájtok alapján.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11
from typing import BinaryIO
from core.kernel.config.config_loader import settings
from apps.kb.kb_ingest.security.ArchiveGuard import ArchiveGuard
from apps.kb.kb_ingest.security.ReadingArchiveError import ReadingArchiveError
from apps.kb.kb_ingest.config.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.kb_ingest.validation.ValidateFile import extension_from_filename
from apps.kb.shared.errors import KbValidationError
from apps.kb.kb_ingest.security.PdfGuard import PdfGuard
from apps.kb.kb_ingest.security.ReadingSecurityError import ReadingSecurityError

GENERIC_ALLOWED_MIME = frozenset({"application/octet-stream"})
ALLOWED_MIME_BY_EXT: dict[str, frozenset[str]] = {
    ".txt": frozenset({"text/plain"}),
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
    ),
}
class FileSniffer:
    """Fájl típus felismerő a fejléc bájtok alapján."""
    def __init__(
        self,
        *,
        config: ReadingConfig | None = None,
        archive_guard: ArchiveGuard | None = None,
        pdf_guard: PdfGuard | None = None,
    ) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._config = config or DEFAULT_READING_CONFIG
        self._archive_guard = archive_guard or ArchiveGuard()
        self._pdf_guard = pdf_guard or PdfGuard()

    def sniff_magic_type(self, raw: bytes) -> str:
        """Felismeri a fájl típusát a fejléc bájtok alapján."""
        if raw.startswith(b"%PDF-"):
            return "application/pdf"
        if raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06") or raw.startswith(b"PK\x07\x08"):
            return "application/zip"
        if b"\x00" in raw[:4096]:
            return "application/octet-stream"
        try:
            raw[:8192].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            return "application/octet-stream"

    def validate_mime_type(self, filename: str, mime_type: str | None) -> None:
        """A modul egyik műveletét hajtja végre."""
        ext = extension_from_filename(filename)
        if ext not in self._config.allowed_extensions:
            allowed = ", ".join(sorted(self._config.allowed_extensions))
            raise KbValidationError(f"Unsupported file extension. Allowed: {allowed}")
        normalized_mime = str(mime_type or "").strip().lower()
        if not normalized_mime:
            return
        allowed_for_ext = ALLOWED_MIME_BY_EXT.get(ext, frozenset())
        if normalized_mime in allowed_for_ext or normalized_mime in GENERIC_ALLOWED_MIME:
            return
        raise KbValidationError(f"MIME type '{normalized_mime}' is not allowed for '{ext}'")

    def validate_magic_sample(self, filename: str, sample: bytes) -> None:
        """A modul egyik műveletét hajtja végre."""
        if not bool(getattr(settings, "upload_magic_sniff_enabled", True)):
            return
        ext = extension_from_filename(filename)
        magic_type = self.sniff_magic_type(sample)
        if ext == ".pdf" and magic_type != "application/pdf":
            raise KbValidationError("Uploaded file content does not match PDF format.")
        if ext == ".txt" and magic_type not in {"text/plain"}:
            raise KbValidationError("Uploaded file content does not match text format.")
        if ext == ".docx" and magic_type != "application/zip":
            raise KbValidationError("Uploaded file content does not match DOCX format.")

    def validate_file_content(self, filename: str, raw: bytes) -> None:
        """A modul egyik műveletét hajtja végre."""
        if not raw:
            raise KbValidationError("Uploaded file is empty.")
        sample = raw[:8192]
        self.validate_magic_sample(filename, sample)
        self._pdf_guard.guard_pdf_limits(filename, raw)
        if extension_from_filename(filename) == ".docx":
            try:
                self._archive_guard.inspect_docx_bytes_or_raise(raw)
            except ReadingArchiveError as exc:
                raise KbValidationError(str(exc)) from exc

    def validate_file_content_from_stream(self, filename: str, fileobj: BinaryIO) -> bytes:
        """A modul egyik műveletét hajtja végre."""
        fileobj.seek(0)
        raw = fileobj.read()
        self.validate_file_content(filename, raw)
        fileobj.seek(0)
        return raw
__all__ = [
    "ALLOWED_MIME_BY_EXT",
    "FileSniffer",
    "GENERIC_ALLOWED_MIME",
]
