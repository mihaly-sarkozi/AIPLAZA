from __future__ import annotations

import re
from collections import Counter
from typing import Any

from apps.kb.kb_understanding.config.UnderstandingConf import DEFAULT_UNDERSTANDING_CONFIG, UnderstandingConfig
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.enums.NormalizeStatus import NormalizeStatus
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_metadata import is_ocr_source, slim_metadata_for_downstream
from apps.kb.kb_understanding.mapper.content_mapper import (
    normalized_part_from_extracted,
    normalized_summary_to_orm,
)
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateNormalizedContent import ValidateNormalizedContent
from apps.kb.shared.ids import new_id

_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:-\s*)?(?:page\s+)?\d{1,4}(?:\s*[./]\s*\d{1,4})?(?:\s*-)?(?:\s*\.?\s*oldal)?\s*$",
    re.IGNORECASE,
)
_HEADER_FOOTER_MIN_OCCURRENCES = 3
_HEADER_FOOTER_MAX_LENGTH = 80


class NormalizeContentService:
    def __init__(
        self,
        content_repository: ContentRepository,
        *,
        config: UnderstandingConfig | None = None,
    ) -> None:
        self._content_repository = content_repository
        self._config = config or DEFAULT_UNDERSTANDING_CONFIG
        self._validate = ValidateNormalizedContent()

    def run(self, ctx: UnderstandingJobContext, extracted: ExtractedContentDto) -> NormalizedContentDto:
        batch_size = self._config.normalize_batch_size
        part_types = {item.value for item in NORMALIZABLE_PART_TYPES}
        input_parts = self._content_repository.count_normalizable_extracted_parts(ctx.training_item_id)
        if input_parts <= 0 and not extracted.parts:
            input_parts = sum(
                1 for part in extracted.parts if part.part_type in part_types and (part.text or "").strip()
            )

        self._content_repository.delete_normalized_by_training_item(ctx.training_item_id)
        summary_id = new_id("und_norm")
        self._content_repository.create_normalized_summary(
            normalized_summary_to_orm(
                ctx,
                normalized_content_id=summary_id,
                status=NormalizeStatus.PROCESSING.value,
            )
        )

        applied: dict[str, Any] = {"normalized_part_types": sorted(part_types)}
        normalized_parts = 0
        skipped_parts = 0
        failed_parts = 0
        total_chars = 0

        try:
            for batch in self._content_repository.iter_normalizable_extracted_parts(
                ctx.training_item_id,
                batch_size=batch_size,
                part_types=part_types,
            ):
                normalized_batch = []
                for extracted_part in batch:
                    try:
                        normalized_text, part_applied = self._normalize_part_text(extracted_part.text or "")
                        for key, value in part_applied.items():
                            applied[key] = applied.get(key, 0) + value
                        if not normalized_text.strip():
                            skipped_parts += 1
                            continue
                        raw_metadata = dict(getattr(extracted_part, "metadata_json", None) or {})
                        metadata = slim_metadata_for_downstream(raw_metadata)
                        metadata["source_part_id"] = getattr(extracted_part, "id", None)
                        metadata["part_type"] = getattr(extracted_part, "part_type", None)
                        metadata["page_number"] = getattr(extracted_part, "page_number", None)
                        metadata["part_index"] = getattr(extracted_part, "part_index", None)
                        if is_ocr_source(metadata):
                            metadata["is_from_ocr"] = True
                        normalized_batch.append(
                            normalized_part_from_extracted(
                                ctx,
                                normalized_content_id=summary_id,
                                extracted_part=extracted_part,
                                normalized_text=normalized_text,
                                metadata_json=metadata,
                            )
                        )
                        normalized_parts += 1
                        total_chars += len(normalized_text)
                    except Exception as exc:
                        failed_parts += 1
                        normalized_batch.append(
                            normalized_part_from_extracted(
                                ctx,
                                normalized_content_id=summary_id,
                                extracted_part=extracted_part,
                                normalized_text="",
                                metadata_json=slim_metadata_for_downstream(
                                    dict(getattr(extracted_part, "metadata_json", None) or {})
                                ),
                                status="failed",
                                error_code=UnderstandingErrorCode.NORMALIZATION_FAILED.value,
                                error_message=str(exc)[:1000],
                            )
                        )
                self._content_repository.bulk_insert_normalized_parts(normalized_batch)
        except Exception as exc:
            self._content_repository.finalize_normalized_summary(
                summary_id,
                patch={
                    "status": NormalizeStatus.FAILED.value,
                    "part_count": normalized_parts,
                    "total_chars": total_chars,
                    "char_count": total_chars,
                    "metadata_json": {"applied_rules": applied, "error": str(exc)[:1000]},
                },
            )
            raise UnderstandingProcessingError(UnderstandingErrorCode.NORMALIZATION_FAILED) from exc

        if normalized_parts <= 0:
            status = NormalizeStatus.FAILED
        elif failed_parts > 0:
            status = NormalizeStatus.PARTIAL
        else:
            status = NormalizeStatus.COMPLETED

        trace_summary = {
            "input_parts": input_parts,
            "normalized_parts": normalized_parts,
            "skipped_parts": skipped_parts,
            "total_chars": total_chars,
            "batch_size": batch_size,
            "status": status.value.upper(),
        }
        if failed_parts:
            trace_summary["failed_parts"] = failed_parts

        self._content_repository.finalize_normalized_summary(
            summary_id,
            patch={
                "status": status.value,
                "part_count": normalized_parts,
                "total_chars": total_chars,
                "char_count": total_chars,
                "metadata_json": {"applied_rules": applied, "trace_summary": trace_summary},
            },
        )

        result = NormalizedContentDto(
            normalized_content_id=summary_id,
            status=status.value,
            part_count=normalized_parts,
            total_chars=total_chars,
            char_count=total_chars,
            applied_rules=applied,
            trace_summary=trace_summary,
        )
        self._validate(result)
        return result

    def _normalize_part_text(self, text: str) -> tuple[str, dict[str, int]]:
        applied: dict[str, int] = {}
        text, count = self._fix_encoding(text)
        applied["fixed_encoding"] = count
        lines = text.split("\n")
        lines, count = self._remove_page_number_lines(lines)
        applied["removed_page_number_lines"] = count
        lines, count = self._remove_repeated_lines(lines)
        applied["removed_header_footer_lines"] = count
        lines, count = self._dedupe_consecutive_lines(lines)
        applied["deduplicated_lines"] = count
        text = "\n".join(lines)
        text, count = self._collapse_whitespace(text)
        applied["collapsed_whitespace"] = count
        return text, applied

    @staticmethod
    def _fix_encoding(text: str) -> tuple[str, int]:
        replacements = {
            "\r\n": "\n",
            "\r": "\n",
            "\u00a0": " ",
            "\u200b": "",
            "\ufeff": "",
            "\ufffd": "",
        }
        count = 0
        for source, target in replacements.items():
            occurrences = text.count(source)
            if occurrences:
                count += occurrences
                text = text.replace(source, target)
        return text, count

    @staticmethod
    def _remove_page_number_lines(lines: list[str]) -> tuple[list[str], int]:
        kept = [line for line in lines if not _PAGE_NUMBER_LINE.match(line)]
        return kept, len(lines) - len(kept)

    @staticmethod
    def _remove_repeated_lines(lines: list[str]) -> tuple[list[str], int]:
        stripped = [line.strip() for line in lines]
        counts = Counter(
            line for line in stripped if line and len(line) <= _HEADER_FOOTER_MAX_LENGTH
        )
        repeated = {
            line for line, occurrences in counts.items() if occurrences >= _HEADER_FOOTER_MIN_OCCURRENCES
        }
        if not repeated:
            return lines, 0
        kept = [line for line in lines if line.strip() not in repeated]
        return kept, len(lines) - len(kept)

    @staticmethod
    def _dedupe_consecutive_lines(lines: list[str]) -> tuple[list[str], int]:
        kept: list[str] = []
        removed = 0
        previous: str | None = None
        for line in lines:
            current = line.strip()
            if current and current == previous:
                removed += 1
                continue
            kept.append(line)
            previous = current
        return kept, removed

    @staticmethod
    def _collapse_whitespace(text: str) -> tuple[str, int]:
        before = len(text)
        text = "\n".join(re.sub(r"[ \t]+", " ", line).rstrip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip(), before - len(text)


__all__ = ["NormalizeContentService"]
