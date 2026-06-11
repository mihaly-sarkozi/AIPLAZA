from __future__ import annotations

# backend/apps/kb/kb_ingest/security/PdfGuard.py
# Feladat: PDF méret és oldalszám ellenőrző.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11
from apps.kb.kb_ingest.security.ReadingSecurityError import ReadingSecurityError
from core.kernel.config.config_loader import settings
from apps.kb.kb_ingest.validation.ValidateFile import extension_from_filename

class PdfGuard:
    """Dokumentum fájl méret és oldalszám ellenőrző."""
    def page_count_heuristic(self, raw: bytes) -> int:
        """Oldalszámot becsül a fájl fejlécéből."""
        return max(0, int(raw.count(b"/Type /Page")))

    def guard_pdf_limits(self, filename: str, raw: bytes) -> int:
        """Ellenőrzi a dokumentum méretkorlátjait."""
        if extension_from_filename(filename) != ".pdf":
            return 0
        estimated_pages = self.page_count_heuristic(raw)
        self.guard_pdf_page_count(filename, estimated_pages)
        return estimated_pages

    def guard_pdf_page_count(self, filename: str, estimated_pages: int) -> None:
        """Ellenőrzi a dokumentum oldalszámát."""
        if extension_from_filename(filename) != ".pdf":
            return
        max_pages = max(1, int(getattr(settings, "upload_pdf_max_pages", 200) or 200))
        if int(estimated_pages) > max_pages:
            raise ReadingSecurityError(
                f"PDF too large: page count exceeds limit ({max_pages}).",
            )

__all__ = ['PdfGuard']
