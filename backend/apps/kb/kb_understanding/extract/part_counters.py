from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart


@dataclass
class PartCounters:
    text_parts: int = 0
    table_parts: int = 0
    ocr_text_parts: int = 0
    ocr_empty_parts: int = 0
    ocr_failed_parts: int = 0
    unknown_parts: int = 0
    total_chars: int = 0
    total_parts: int = 0

    def add_parts(self, parts: list[ExtractPart]) -> None:
        for part in parts:
            self.total_parts += 1
            self.total_chars += int(part.char_count or 0)
            if part.part_type == "TEXT":
                self.text_parts += 1
            elif part.part_type == "TABLE":
                self.table_parts += 1
            elif part.part_type == "OCR_TEXT":
                self.ocr_text_parts += 1
            elif part.part_type == "OCR_EMPTY":
                self.ocr_empty_parts += 1
            elif part.part_type == "OCR_FAILED":
                self.ocr_failed_parts += 1
            elif part.part_type == "UNKNOWN":
                self.unknown_parts += 1

    def to_dict(self) -> dict[str, int]:
        return {
            "text_parts": self.text_parts,
            "table_parts": self.table_parts,
            "ocr_text_parts": self.ocr_text_parts,
            "ocr_empty_parts": self.ocr_empty_parts,
            "ocr_failed_parts": self.ocr_failed_parts,
            "unknown_parts": self.unknown_parts,
            "total_chars": self.total_chars,
            "total_parts": self.total_parts,
        }


__all__ = ["PartCounters"]
