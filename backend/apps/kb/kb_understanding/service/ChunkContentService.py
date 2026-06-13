from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.config.UnderstandingConf import (
    DEFAULT_UNDERSTANDING_CONFIG,
    UnderstandingConfig,
)
from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.mapper.chunk_mapper import chunk_dto_to_orm
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.validation.ValidateChunks import ValidateChunks
from apps.kb.shared.ids import new_id

_BLOCK_TO_CHUNK_TYPE = {
    StructuredBlockType.LIST: ChunkType.LIST,
    StructuredBlockType.TABLE: ChunkType.TABLE,
    StructuredBlockType.FAQ: ChunkType.FAQ,
    StructuredBlockType.STEP: ChunkType.STEP,
    StructuredBlockType.NOTE: ChunkType.NOTE,
    StructuredBlockType.WARNING: ChunkType.WARNING,
}


@dataclass
class _PendingChunk:
    texts: list[str] = field(default_factory=list)
    block_types: list[StructuredBlockType] = field(default_factory=list)
    page_number: int | None = None
    section_title: str | None = None
    source_part_ids: list[str | None] = field(default_factory=list)
    page_numbers: list[int | None] = field(default_factory=list)
    block_kinds: list[str | None] = field(default_factory=list)
    heading_path: list[str] = field(default_factory=list)
    table_refs: list[dict[str, Any]] = field(default_factory=list)
    bbox_refs: list[dict[str, Any] | None] = field(default_factory=list)

    @property
    def length(self) -> int:
        return sum(len(text) for text in self.texts) + 2 * max(0, len(self.texts) - 1)

    @property
    def text(self) -> str:
        return "\n\n".join(self.texts)


class ChunkContentService:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        config: UnderstandingConfig = DEFAULT_UNDERSTANDING_CONFIG,
    ) -> None:
        self._chunk_repository = chunk_repository
        self._config = config
        self._validate = ValidateChunks()

    def run(self, ctx: UnderstandingJobContext, blocks: list[StructuredBlockDto]) -> list[KnowledgeChunkDto]:
        chunks = self._build_chunks(blocks)
        self._validate(chunks)
        version = self._chunk_repository.max_version_for_document(ctx.training_item_id) + 1
        self._chunk_repository.replace_for_document(
            ctx.training_item_id,
            [chunk_dto_to_orm(ctx, chunk, version=version) for chunk in chunks],
        )
        return chunks

    def _build_chunks(self, blocks: list[StructuredBlockDto]) -> list[KnowledgeChunkDto]:
        pending_chunks: list[_PendingChunk] = []
        current = _PendingChunk()
        current_section: str | None = None

        for block in blocks:
            if block.block_type in (StructuredBlockType.TITLE, StructuredBlockType.HEADING):
                if current.texts:
                    pending_chunks.append(current)
                current = _PendingChunk(
                    texts=[block.text],
                    block_types=[block.block_type],
                    page_number=block.page_number,
                    section_title=block.text[:512],
                    source_part_ids=[block.metadata.get("source_part_id")],
                    page_numbers=[block.page_number],
                    block_kinds=[block.metadata.get("block_kind")],
                    heading_path=list(block.metadata.get("heading_path") or [block.text[:512]]),
                    table_refs=[self._table_ref(block.metadata)],
                    bbox_refs=[block.metadata.get("bbox")],
                )
                current_section = block.text[:512]
                continue

            section = block.section_title or current_section
            section_changed = current.texts and current.section_title not in (None, section)
            would_overflow = current.length + len(block.text) > self._config.chunk_max_chars
            if current.texts and (section_changed or would_overflow):
                pending_chunks.append(current)
                current = _PendingChunk()

            if not current.texts:
                current.page_number = block.page_number
                current.section_title = section
                current.heading_path = list(block.metadata.get("heading_path") or [])
            current.texts.append(block.text)
            current.block_types.append(block.block_type)
            current.source_part_ids.append(block.metadata.get("source_part_id"))
            current.page_numbers.append(block.page_number)
            current.block_kinds.append(block.metadata.get("block_kind"))
            table_ref = self._table_ref(block.metadata)
            if table_ref:
                current.table_refs.append(table_ref)
            current.bbox_refs.append(block.metadata.get("bbox"))

        if current.texts:
            pending_chunks.append(current)

        merged = self._merge_short(pending_chunks)
        return self._finalize(merged)

    @staticmethod
    def _table_ref(metadata: dict[str, Any]) -> dict[str, Any] | None:
        if not metadata.get("headers") and not metadata.get("rows"):
            return None
        return {
            "table_index": metadata.get("table_index"),
            "headers": metadata.get("headers"),
            "row_count": metadata.get("row_count"),
            "column_count": metadata.get("column_count"),
        }

    def _merge_short(self, chunks: list[_PendingChunk]) -> list[_PendingChunk]:
        merged: list[_PendingChunk] = []
        for chunk in chunks:
            if (
                merged
                and chunk.length < self._config.chunk_min_chars
                and merged[-1].length + chunk.length <= self._config.chunk_max_chars
            ):
                previous = merged[-1]
                previous.texts.extend(chunk.texts)
                previous.block_types.extend(chunk.block_types)
                previous.source_part_ids.extend(chunk.source_part_ids)
                previous.page_numbers.extend(chunk.page_numbers)
                previous.block_kinds.extend(chunk.block_kinds)
                previous.table_refs.extend(chunk.table_refs)
                previous.bbox_refs.extend(chunk.bbox_refs)
                if chunk.heading_path:
                    previous.heading_path = chunk.heading_path
                continue
            merged.append(chunk)
        return merged

    def _finalize(self, chunks: list[_PendingChunk]) -> list[KnowledgeChunkDto]:
        result: list[KnowledgeChunkDto] = []
        order_index = 0
        for chunk in chunks:
            metadata = {
                "source_part_ids": [part_id for part_id in chunk.source_part_ids if part_id],
                "page_numbers": sorted({page for page in chunk.page_numbers if page is not None}),
                "section_title": chunk.section_title,
                "heading_path": chunk.heading_path,
                "block_kinds": [kind for kind in chunk.block_kinds if kind],
                "table_refs": chunk.table_refs,
                "bbox_refs": [bbox for bbox in chunk.bbox_refs if bbox],
            }
            for part in self._split_long(chunk.text):
                result.append(
                    KnowledgeChunkDto(
                        chunk_id=new_id("chunk"),
                        text=part,
                        chunk_type=self._chunk_type(chunk.block_types),
                        order_index=order_index,
                        token_count=max(1, int(len(part) / self._config.token_chars_ratio)),
                        checksum=hashlib.sha256(part.encode("utf-8")).hexdigest(),
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
    def _chunk_type(block_types: list[StructuredBlockType]) -> ChunkType:
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
