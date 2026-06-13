from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from apps.kb.kb_understanding.chunk.NormalizedPartBlockClassifier import (
    LogicalBlockType,
    NormalizedPartBlockClassifier,
)
from apps.kb.kb_understanding.chunk.chunk_metadata import build_uniform_chunk_metadata
from apps.kb.kb_understanding.chunk.language_hints import collect_language_hint_fields
from apps.kb.kb_understanding.chunk.parent_chunk_hash import (
    compute_parent_chunk_hash,
    parent_chunk_id_from_hash,
)
from apps.kb.kb_understanding.config.UnderstandingConf import (
    DEFAULT_UNDERSTANDING_CONFIG,
    UnderstandingConfig,
)
from apps.kb.kb_understanding.dto.ChunkContentResultDto import ChunkContentResultDto
from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.extract.extract_metadata import is_ocr_source
from apps.kb.kb_understanding.extract.heading_path import HeadingPathTracker
from apps.kb.kb_understanding.mapper.chunk_mapper import chunk_dto_to_orm
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateChunks import ValidateChunks
from apps.kb.shared.ids import new_id

logger = logging.getLogger(__name__)

_BLOCK_TO_CHUNK_TYPE = {
    LogicalBlockType.LIST: ChunkType.LIST,
    LogicalBlockType.TABLE: ChunkType.TABLE,
    LogicalBlockType.FAQ: ChunkType.FAQ,
    LogicalBlockType.STEP: ChunkType.STEP,
    LogicalBlockType.NOTE: ChunkType.NOTE,
    LogicalBlockType.WARNING: ChunkType.WARNING,
}

_HEADING_TYPES = frozenset({LogicalBlockType.TITLE, LogicalBlockType.HEADING})
_SKIP_TYPES = frozenset({LogicalBlockType.HEADER, LogicalBlockType.FOOTER})


@dataclass
class _ClassifiedPart:
    text: str
    block_type: LogicalBlockType
    page_number: int | None
    section_title: str | None
    source_normalized_part_id: str | None
    source_part_id: str | None
    is_from_ocr: bool
    metadata: dict[str, Any]


@dataclass
class _PendingChunk:
    texts: list[str] = field(default_factory=list)
    block_types: list[LogicalBlockType] = field(default_factory=list)
    page_number: int | None = None
    section_title: str | None = None
    source_normalized_part_ids: list[str | None] = field(default_factory=list)
    source_part_ids: list[str | None] = field(default_factory=list)
    page_numbers: list[int | None] = field(default_factory=list)
    document_orders: list[int | None] = field(default_factory=list)
    block_kinds: list[str | None] = field(default_factory=list)
    heading_path: list[str] = field(default_factory=list)
    heading_levels: list[int] = field(default_factory=list)
    style_names: list[str | None] = field(default_factory=list)
    table_refs: list[dict[str, Any]] = field(default_factory=list)
    bbox_refs: list[dict[str, Any] | None] = field(default_factory=list)
    ocr_confidences: list[float] = field(default_factory=list)
    ocr_language_values: list[str | None] = field(default_factory=list)
    is_from_ocr: bool = False
    has_extractor_parts: bool = False

    @property
    def length(self) -> int:
        return sum(len(text) for text in self.texts) + 2 * max(0, len(self.texts) - 1)

    @property
    def text(self) -> str:
        return "\n\n".join(self.texts)

    @property
    def is_table_only(self) -> bool:
        return bool(self.block_types) and all(
            block_type == LogicalBlockType.TABLE for block_type in self.block_types
        )


@dataclass
class _ChunkStats:
    input_parts: int = 0
    merged_chunks: int = 0
    split_chunks: int = 0
    table_chunks: int = 0
    ocr_chunks: int = 0
    headers_skipped: int = 0
    footers_skipped: int = 0

    def observe(self, block_type: LogicalBlockType) -> None:
        self.input_parts += 1
        if block_type == LogicalBlockType.HEADER:
            self.headers_skipped += 1
        elif block_type == LogicalBlockType.FOOTER:
            self.footers_skipped += 1


class ChunkContentService:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        content_repository: ContentRepository,
        *,
        config: UnderstandingConfig = DEFAULT_UNDERSTANDING_CONFIG,
        classifier: NormalizedPartBlockClassifier | None = None,
    ) -> None:
        self._chunk_repository = chunk_repository
        self._content_repository = content_repository
        self._config = config
        self._classifier = classifier or NormalizedPartBlockClassifier()
        self._validate = ValidateChunks()

    def run(self, ctx: UnderstandingJobContext, normalized: NormalizedContentDto) -> ChunkContentResultDto:
        classified_parts, stats = self._classify_normalized_parts(ctx, normalized)
        chunks, stats = self._build_chunks(ctx, classified_parts, stats)
        validation = self._validate(chunks)
        for warning in validation.warnings:
            logger.warning("Chunk validation warning (item=%s): %s", ctx.training_item_id, warning)

        version = self._chunk_repository.max_version_for_document(ctx.training_item_id) + 1
        self._chunk_repository.replace_for_document(
            ctx.training_item_id,
            self._iter_chunk_orms(ctx, chunks, version=version),
            batch_size=self._config.chunk_insert_batch_size,
        )
        trace_summary = {
            "input_parts": stats.input_parts,
            "chunks_created": len(chunks),
            "table_chunks": stats.table_chunks,
            "split_chunks": stats.split_chunks,
            "merged_chunks": stats.merged_chunks,
            "ocr_chunks": stats.ocr_chunks,
            "headers_skipped": stats.headers_skipped,
            "footers_skipped": stats.footers_skipped,
        }
        if validation.warnings:
            trace_summary["validation_warnings"] = list(validation.warnings)
        return ChunkContentResultDto(chunks=chunks, trace_summary=trace_summary)

    @staticmethod
    def _iter_chunk_orms(
        ctx: UnderstandingJobContext,
        chunks: list[KnowledgeChunkDto],
        *,
        version: int,
    ) -> Iterator:
        for chunk in chunks:
            yield chunk_dto_to_orm(ctx, chunk, version=version)

    def _classify_normalized_parts(
        self,
        ctx: UnderstandingJobContext,
        normalized: NormalizedContentDto,
    ) -> tuple[list[_ClassifiedPart], _ChunkStats]:
        parts: list[_ClassifiedPart] = []
        stats = _ChunkStats()
        heading_tracker = HeadingPathTracker()
        seen_parts = 0

        for batch in self._content_repository.iter_normalized_parts_for_item(
            ctx.training_item_id,
            batch_size=self._config.normalize_batch_size,
        ):
            for part in batch:
                block_text = (part.normalized_text or "").strip()
                if not block_text:
                    continue

                metadata = dict(part.metadata_json or {})
                metadata.setdefault("source_part_id", part.source_part_id)
                metadata.setdefault("source_normalized_part_id", getattr(part, "id", None))
                metadata.setdefault("part_type", part.part_type)
                metadata.setdefault("page_number", part.page_number)
                metadata.setdefault("part_index", part.part_index)
                metadata.setdefault("document_order", part.document_order)
                if is_ocr_source(metadata):
                    metadata["is_from_ocr"] = True

                block_type = self._classifier.classify(
                    text=block_text,
                    metadata=metadata,
                    is_first=seen_parts == 0,
                )
                stats.observe(block_type)
                seen_parts += 1

                if block_type in _SKIP_TYPES:
                    continue

                path_info = self._resolve_heading_path(
                    heading_tracker,
                    metadata=metadata,
                    block_text=block_text,
                    block_type=block_type,
                )
                block_metadata = self._build_part_metadata(metadata, path_info)
                section_title = path_info.get("current_section_title")
                parts.append(
                    _ClassifiedPart(
                        text=block_text,
                        block_type=block_type,
                        page_number=part.page_number,
                        section_title=section_title
                        if block_type not in (_HEADING_TYPES | _SKIP_TYPES)
                        else None,
                        source_normalized_part_id=getattr(part, "id", None),
                        source_part_id=part.source_part_id,
                        is_from_ocr=bool(block_metadata.get("is_from_ocr")),
                        metadata=block_metadata,
                    )
                )

        if not parts and normalized.text.strip():
            parts, stats = self._classify_legacy_text(normalized)

        return parts, stats

    def _classify_legacy_text(self, normalized: NormalizedContentDto) -> tuple[list[_ClassifiedPart], _ChunkStats]:
        parts: list[_ClassifiedPart] = []
        stats = _ChunkStats()
        section_title: str | None = None
        offset = 0

        for raw_block in self._split_blocks(normalized.text):
            block_text = raw_block.strip()
            start_offset = normalized.text.find(raw_block, offset)
            if start_offset >= 0:
                offset = start_offset + len(raw_block)
            page_number = self._page_for_offset(normalized.page_map, max(start_offset, 0))
            block_type = self._classifier.classify(
                text=block_text,
                metadata={},
                is_first=not parts,
            )
            stats.observe(block_type)
            if block_type in _SKIP_TYPES:
                continue
            if block_type in _HEADING_TYPES:
                section_title = block_text[:512]
                current_section = None if block_type == LogicalBlockType.TITLE else section_title
            else:
                current_section = section_title
            parts.append(
                _ClassifiedPart(
                    text=block_text,
                    block_type=block_type,
                    page_number=page_number,
                    section_title=current_section,
                    source_normalized_part_id=None,
                    source_part_id=None,
                    is_from_ocr=False,
                    metadata={"heading_path": [section_title] if section_title else []},
                )
            )
        return parts, stats

    @staticmethod
    def _resolve_heading_path(
        heading_tracker: HeadingPathTracker,
        *,
        metadata: dict[str, Any],
        block_text: str,
        block_type: LogicalBlockType,
    ) -> dict[str, Any]:
        if metadata.get("heading_path"):
            return {
                "heading_path": list(metadata.get("heading_path") or []),
                "heading_levels": list(metadata.get("heading_levels") or []),
                "current_section_title": metadata.get("current_section_title")
                or (metadata.get("heading_path") or [None])[-1],
            }
        if block_type in _HEADING_TYPES:
            level = metadata.get("heading_level")
            if level is None:
                level = 0 if block_type == LogicalBlockType.TITLE else 1
            return heading_tracker.update(int(level), block_text)
        return heading_tracker.current()

    @staticmethod
    def _build_part_metadata(entry: dict[str, Any], path_info: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_part_id": entry.get("source_part_id"),
            "source_normalized_part_id": entry.get("source_normalized_part_id"),
            "document_order": entry.get("document_order"),
            "part_index": entry.get("part_index"),
            "part_type": entry.get("part_type"),
            "block_kind": entry.get("block_kind"),
            "page_number": entry.get("page_number") or entry.get("page"),
            "style_name": entry.get("style_name"),
            "style_id": entry.get("style_id"),
            "heading_level": entry.get("heading_level"),
            "is_heading": entry.get("is_heading"),
            "is_list": entry.get("is_list"),
            "list_level": entry.get("list_level"),
            "numbering_id": entry.get("numbering_id"),
            "numbering_level": entry.get("numbering_level"),
            "list_marker": entry.get("list_marker"),
            "runs": entry.get("runs"),
            "bbox": entry.get("bbox"),
            "font_names": entry.get("font_names"),
            "font_sizes": entry.get("font_sizes"),
            "dominant_font_size": entry.get("dominant_font_size"),
            "is_bold_guess": entry.get("is_bold_guess"),
            "is_heading_guess": entry.get("is_heading_guess"),
            "heading_confidence": entry.get("heading_confidence"),
            "is_header_candidate": entry.get("is_header_candidate"),
            "is_footer_candidate": entry.get("is_footer_candidate"),
            "header_footer_confidence": entry.get("header_footer_confidence"),
            "table_index": entry.get("table_index"),
            "headers": entry.get("headers"),
            "rows": entry.get("rows"),
            "row_count": entry.get("row_count"),
            "column_count": entry.get("column_count"),
            "ocr_confidence": entry.get("ocr_confidence"),
            "ocr_language": entry.get("ocr_language"),
            "is_from_ocr": is_ocr_source(entry),
            "heading_path": list(path_info.get("heading_path") or []),
            "heading_levels": list(path_info.get("heading_levels") or []),
            "current_section_title": path_info.get("current_section_title"),
        }

    def _build_chunks(
        self,
        ctx: UnderstandingJobContext,
        parts: list[_ClassifiedPart],
        stats: _ChunkStats,
    ) -> tuple[list[KnowledgeChunkDto], _ChunkStats]:
        if not parts:
            raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)

        pending_chunks: list[_PendingChunk] = []
        current = _PendingChunk()
        current_section: str | None = None

        for part in parts:
            if part.block_type in _HEADING_TYPES:
                if current.texts:
                    pending_chunks.append(current)
                current = self._seed_pending(part)
                current_section = part.metadata.get("current_section_title") or part.text[:512]
                continue

            if part.block_type == LogicalBlockType.TABLE:
                if current.texts:
                    pending_chunks.append(current)
                    current = _PendingChunk()
                pending_chunks.append(self._seed_pending(part))
                continue

            section = part.section_title or part.metadata.get("current_section_title") or current_section
            section_changed = current.texts and current.section_title not in (None, section)
            would_overflow = current.length + len(part.text) > self._config.chunk_max_chars
            if current.texts and (section_changed or would_overflow):
                pending_chunks.append(current)
                current = _PendingChunk()

            if not current.texts:
                current.page_number = part.page_number
                current.section_title = section
                current.heading_path = list(part.metadata.get("heading_path") or [])
                current.heading_levels = list(part.metadata.get("heading_levels") or [])
            self._append_part(current, part)

        if current.texts:
            pending_chunks.append(current)

        merged = self._merge_short(pending_chunks, stats)
        chunks = self._finalize(ctx, merged, stats)
        return chunks, stats

    @staticmethod
    def _seed_pending(part: _ClassifiedPart) -> _PendingChunk:
        pending = _PendingChunk(
            texts=[part.text],
            block_types=[part.block_type],
            page_number=part.page_number,
            section_title=part.metadata.get("current_section_title") or part.text[:512],
            source_normalized_part_ids=[part.source_normalized_part_id],
            source_part_ids=[part.source_part_id],
            page_numbers=[part.page_number],
            document_orders=[part.metadata.get("document_order")],
            block_kinds=[part.metadata.get("block_kind")],
            heading_path=list(part.metadata.get("heading_path") or [part.text[:512]]),
            heading_levels=list(part.metadata.get("heading_levels") or []),
            style_names=[part.metadata.get("style_name")],
            table_refs=[ChunkContentService._table_ref(part.metadata)],
            bbox_refs=[part.metadata.get("bbox")],
        )
        if part.is_from_ocr:
            pending.is_from_ocr = True
            if part.metadata.get("ocr_confidence") is not None:
                pending.ocr_confidences.append(float(part.metadata["ocr_confidence"]))
            pending.ocr_language_values.append(part.metadata.get("ocr_language"))
        else:
            pending.has_extractor_parts = True
        return pending

    @staticmethod
    def _append_part(pending: _PendingChunk, part: _ClassifiedPart) -> None:
        pending.texts.append(part.text)
        pending.block_types.append(part.block_type)
        pending.source_normalized_part_ids.append(part.source_normalized_part_id)
        pending.source_part_ids.append(part.source_part_id)
        pending.page_numbers.append(part.page_number)
        pending.document_orders.append(part.metadata.get("document_order"))
        pending.block_kinds.append(part.metadata.get("block_kind"))
        pending.style_names.append(part.metadata.get("style_name"))
        table_ref = ChunkContentService._table_ref(part.metadata)
        if table_ref:
            pending.table_refs.append(table_ref)
        pending.bbox_refs.append(part.metadata.get("bbox"))
        if part.is_from_ocr:
            pending.is_from_ocr = True
            if part.metadata.get("ocr_confidence") is not None:
                pending.ocr_confidences.append(float(part.metadata["ocr_confidence"]))
            pending.ocr_language_values.append(part.metadata.get("ocr_language"))
        else:
            pending.has_extractor_parts = True
        if part.metadata.get("heading_path"):
            pending.heading_path = list(part.metadata.get("heading_path") or [])
        if part.metadata.get("heading_levels"):
            pending.heading_levels = list(part.metadata.get("heading_levels") or [])

    @staticmethod
    def _table_ref(metadata: dict[str, Any]) -> dict[str, Any] | None:
        if not metadata.get("headers") and not metadata.get("rows"):
            return None
        return {
            "table_index": metadata.get("table_index"),
            "headers": metadata.get("headers"),
            "rows": metadata.get("rows"),
            "row_count": metadata.get("row_count"),
            "column_count": metadata.get("column_count"),
        }

    def _merge_short(self, chunks: list[_PendingChunk], stats: _ChunkStats) -> list[_PendingChunk]:
        merged: list[_PendingChunk] = []
        for chunk in chunks:
            if chunk.is_table_only:
                merged.append(chunk)
                continue
            if (
                merged
                and not merged[-1].is_table_only
                and chunk.length < self._config.chunk_min_chars
                and merged[-1].length + chunk.length <= self._config.chunk_max_chars
            ):
                previous = merged[-1]
                previous.texts.extend(chunk.texts)
                previous.block_types.extend(chunk.block_types)
                previous.source_normalized_part_ids.extend(chunk.source_normalized_part_ids)
                previous.source_part_ids.extend(chunk.source_part_ids)
                previous.page_numbers.extend(chunk.page_numbers)
                previous.document_orders.extend(chunk.document_orders)
                previous.block_kinds.extend(chunk.block_kinds)
                previous.style_names.extend(chunk.style_names)
                previous.table_refs.extend(chunk.table_refs)
                previous.bbox_refs.extend(chunk.bbox_refs)
                previous.ocr_confidences.extend(chunk.ocr_confidences)
                previous.ocr_language_values.extend(chunk.ocr_language_values)
                previous.is_from_ocr = previous.is_from_ocr or chunk.is_from_ocr
                previous.has_extractor_parts = previous.has_extractor_parts or chunk.has_extractor_parts
                if chunk.heading_path:
                    previous.heading_path = chunk.heading_path
                if chunk.heading_levels:
                    previous.heading_levels = chunk.heading_levels
                stats.merged_chunks += 1
                continue
            merged.append(chunk)
        return merged

    def _finalize(
        self,
        ctx: UnderstandingJobContext,
        chunks: list[_PendingChunk],
        stats: _ChunkStats,
    ) -> list[KnowledgeChunkDto]:
        result: list[KnowledgeChunkDto] = []
        order_index = 0
        for chunk in chunks:
            source_part_ids = [part_id for part_id in chunk.source_part_ids if part_id]
            source_normalized_part_ids = [
                part_id for part_id in chunk.source_normalized_part_ids if part_id
            ]
            page_numbers = sorted({page for page in chunk.page_numbers if page is not None})
            document_orders = sorted({order for order in chunk.document_orders if order is not None})
            block_kinds = [kind for kind in chunk.block_kinds if kind]
            bbox_refs = [bbox for bbox in chunk.bbox_refs if bbox]
            style_names = [name for name in chunk.style_names if name]
            ocr_confidence = (
                round(sum(chunk.ocr_confidences) / len(chunk.ocr_confidences), 4)
                if chunk.ocr_confidences
                else None
            )
            language_hints, language_sources, ocr_languages = collect_language_hint_fields(
                is_from_ocr=chunk.is_from_ocr,
                ocr_language_values=chunk.ocr_language_values,
                has_extractor_parts=chunk.has_extractor_parts or not chunk.is_from_ocr,
            )

            parent_hash = compute_parent_chunk_hash(
                training_item_id=ctx.training_item_id,
                heading_path=chunk.heading_path,
                section_title=chunk.section_title,
                source_part_ids=source_part_ids,
            )
            parent_id = parent_chunk_id_from_hash(parent_hash)
            text_parts = self._split_long(chunk.text)
            split_count = len(text_parts)
            if split_count > 1:
                stats.split_chunks += split_count

            chunk_type = ChunkType.TABLE if chunk.is_table_only else self._chunk_type(chunk.block_types)
            if chunk_type == ChunkType.TABLE:
                stats.table_chunks += 1
            if chunk.is_from_ocr:
                stats.ocr_chunks += 1

            for split_index, part_text in enumerate(text_parts, start=1):
                metadata = build_uniform_chunk_metadata(
                    source_part_ids=source_part_ids,
                    source_normalized_part_ids=source_normalized_part_ids,
                    page_numbers=page_numbers,
                    document_orders=document_orders,
                    section_title=chunk.section_title,
                    heading_path=chunk.heading_path,
                    heading_levels=chunk.heading_levels,
                    block_kinds=block_kinds,
                    table_refs=chunk.table_refs,
                    bbox_refs=bbox_refs,
                    style_names=style_names,
                    is_from_ocr=chunk.is_from_ocr,
                    ocr_confidence=ocr_confidence,
                    split_index=split_index if split_count > 1 else None,
                    split_count=split_count if split_count > 1 else None,
                    parent_chunk_id=parent_id if split_count > 1 else None,
                    parent_chunk_hash=parent_hash if split_count > 1 else None,
                    language_hints=language_hints or None,
                    language_sources=language_sources or None,
                    ocr_languages=ocr_languages or None,
                )
                if chunk.is_table_only and chunk.table_refs:
                    table_ref = chunk.table_refs[0]
                    metadata["headers"] = table_ref.get("headers")
                    metadata["row_count"] = table_ref.get("row_count")
                    metadata["column_count"] = table_ref.get("column_count")

                result.append(
                    KnowledgeChunkDto(
                        chunk_id=new_id("chunk"),
                        text=part_text,
                        chunk_type=chunk_type,
                        order_index=order_index,
                        token_count=max(1, int(len(part_text) / self._config.token_chars_ratio)),
                        checksum=hashlib.sha256(part_text.encode("utf-8")).hexdigest(),
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        metadata=metadata,
                    )
                )
                order_index += 1
        return result

    def _split_long(self, text: str) -> list[str]:
        max_chars = self._config.chunk_max_chars
        overlap = self._config.chunk_overlap_chars
        if len(text) <= max_chars:
            return [text]
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                window = text[start:end]
                cut = max(window.rfind(". "), window.rfind("\n"), window.rfind(" "))
                if cut > max_chars // 2:
                    end = start + cut + 1
            parts.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return [part for part in parts if part]

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        return [block for block in re.split(r"\n\s*\n", text) if block.strip()]

    @staticmethod
    def _page_for_offset(page_map: list[dict[str, Any]], offset: int) -> int | None:
        for entry in page_map:
            if int(entry.get("start", 0)) <= offset < int(entry.get("end", 0)):
                page = entry.get("page")
                return int(page) if page is not None else None
        return None

    @staticmethod
    def _chunk_type(block_types: list[LogicalBlockType]) -> ChunkType:
        counts: dict[ChunkType, int] = {}
        for block_type in block_types:
            mapped = _BLOCK_TO_CHUNK_TYPE.get(block_type)
            if mapped is not None:
                counts[mapped] = counts.get(mapped, 0) + 1
        if not counts:
            return ChunkType.TEXT
        content_blocks = sum(counts.values())
        plain_blocks = len(block_types) - content_blocks
        dominant = max(counts, key=lambda key: counts[key])
        return dominant if counts[dominant] >= plain_blocks else ChunkType.TEXT


__all__ = ["ChunkContentService"]
