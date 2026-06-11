from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateUnderstandingResult.py
# Feladat: A teljes feldolgozás használhatóságának ellenőrzőlistája (validate lépés magja).
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnderstandingChecklist:
    has_extracted_text: bool = False
    has_normalized_text: bool = False
    has_chunks: bool = False
    has_source_link: bool = False
    has_embeddings: bool = False
    has_indexable_data: bool = False
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_complete(self) -> bool:
        """A kereshetőséghez kötelező feltételek (chunk + embedding + forrás)."""
        return (
            self.has_extracted_text
            and self.has_normalized_text
            and self.has_chunks
            and self.has_source_link
            and self.has_embeddings
            and self.has_indexable_data
        )


class ValidateUnderstandingResult:
    def __call__(
        self,
        *,
        extracted_chars: int,
        normalized_chars: int,
        chunk_count: int,
        chunks_with_source: int,
        embedding_count: int,
    ) -> UnderstandingChecklist:
        checks = {
            "extracted_text": extracted_chars > 0,
            "normalized_text": normalized_chars > 0,
            "chunks": chunk_count > 0,
            "source_link": chunk_count > 0 and chunks_with_source == chunk_count,
            "embeddings": embedding_count >= chunk_count > 0,
            "indexable_data": chunk_count > 0 and embedding_count > 0,
        }
        missing = tuple(name for name, passed in checks.items() if not passed)
        return UnderstandingChecklist(
            has_extracted_text=checks["extracted_text"],
            has_normalized_text=checks["normalized_text"],
            has_chunks=checks["chunks"],
            has_source_link=checks["source_link"],
            has_embeddings=checks["embeddings"],
            has_indexable_data=checks["indexable_data"],
            missing=missing,
        )


__all__ = ["UnderstandingChecklist", "ValidateUnderstandingResult"]
