from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnderstandingChecklist:
    has_extracted_content: bool = False
    has_usable_parts: bool = False
    has_normalized_text: bool = False
    has_chunks: bool = False
    has_source_link: bool = False
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_complete(self) -> bool:
        return (
            self.has_extracted_content
            and self.has_usable_parts
            and self.has_normalized_text
            and self.has_chunks
            and self.has_source_link
        )


class ValidateUnderstandingResult:
    def __call__(
        self,
        *,
        has_extracted_content: bool,
        usable_part_count: int,
        normalized_chars: int,
        chunk_count: int,
        chunks_with_source: int,
    ) -> UnderstandingChecklist:
        checks = {
            "extracted_content": has_extracted_content,
            "usable_parts": usable_part_count > 0,
            "normalized_text": normalized_chars > 0,
            "chunks": chunk_count > 0,
            "source_link": chunk_count > 0 and chunks_with_source == chunk_count,
        }
        missing = tuple(name for name, passed in checks.items() if not passed)
        return UnderstandingChecklist(
            has_extracted_content=checks["extracted_content"],
            has_usable_parts=checks["usable_parts"],
            has_normalized_text=checks["normalized_text"],
            has_chunks=checks["chunks"],
            has_source_link=checks["source_link"],
            missing=missing,
        )


__all__ = ["UnderstandingChecklist", "ValidateUnderstandingResult"]
