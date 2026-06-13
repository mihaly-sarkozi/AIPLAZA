from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


@dataclass(frozen=True)
class ChunkValidationResult:
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ValidateChunks:
    def __call__(self, chunks: list[KnowledgeChunkDto]) -> ChunkValidationResult:
        if not chunks:
            raise UnderstandingValidationError(UnderstandingErrorCode.NO_CHUNKS)

        warnings: list[str] = []
        order_indexes = [chunk.order_index for chunk in chunks]
        if sorted(order_indexes) != order_indexes:
            raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)

        for index, chunk in enumerate(chunks):
            prefix = f"chunk[{index}]"
            if not (chunk.text or "").strip():
                raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)
            if not chunk.checksum:
                raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)

            metadata = dict(chunk.metadata or {})
            source_part_ids = metadata.get("source_part_ids") or []
            if not source_part_ids:
                warnings.append(f"{prefix}: missing source_part_ids")

            heading_path = metadata.get("heading_path")
            if heading_path is None or not isinstance(heading_path, list):
                warnings.append(f"{prefix}: heading_path is not a list")

            split_index = metadata.get("split_index")
            split_count = metadata.get("split_count")
            if split_index is not None or split_count is not None:
                if not isinstance(split_index, int) or not isinstance(split_count, int):
                    warnings.append(f"{prefix}: invalid split metadata types")
                elif split_index < 1 or split_count < 1 or split_index > split_count:
                    warnings.append(f"{prefix}: inconsistent split_index/split_count")
                if not metadata.get("parent_chunk_hash"):
                    warnings.append(f"{prefix}: split chunk missing parent_chunk_hash")

            if chunk.chunk_type == ChunkType.TABLE and not metadata.get("table_refs"):
                warnings.append(f"{prefix}: TABLE chunk missing table_refs")

        return ChunkValidationResult(warnings=tuple(warnings))


__all__ = ["ChunkValidationResult", "ValidateChunks"]
