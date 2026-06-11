from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/ManualTextExtractorAdapter.py
# Feladat: Kézi szöveg / sima txt tartalom kinyerése.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto


class ManualTextExtractorAdapter:
    name = "plain_text_v1"

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractedContentDto:
        text = data.decode("utf-8", errors="replace")
        return ExtractedContentDto(
            text=text,
            page_map=[],
            char_count=len(text),
            source_mime=mime_type or "text/plain",
            extractor=self.name,
        )


__all__ = ["ManualTextExtractorAdapter"]
