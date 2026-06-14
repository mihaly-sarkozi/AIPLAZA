from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import SpatialExtractionResult, SpatialMentionDto
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.mapper.discovery_mapper import spatial_dto_to_orm
from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
from apps.kb.kb_discovery.spatial.LocationRecognizer import (
    AddressRecognizer,
    LocationRecognizer,
    RegionRecognizer,
    RoomRecognizer,
)
from apps.kb.kb_discovery.spatial.SpatialContextScorer import SpatialContextScorer


def _text_offsets(text: str, raw_text: str) -> tuple[int | None, int | None]:
    index = text.find(raw_text)
    if index < 0:
        return None, None
    return index, index + len(raw_text)


class SpatialExtractionService:
    def __init__(self, spatial_repository: SpatialRepository) -> None:
        self._spatial_repository = spatial_repository
        self._recognizers = [
            LocationRecognizer(),
            AddressRecognizer(),
            RegionRecognizer(),
            RoomRecognizer(),
        ]
        self._scorer = SpatialContextScorer()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> SpatialExtractionResult:
        mentions: list[SpatialMentionDto] = []
        for chunk in chunks:
            language_code = chunk.language_code or ctx.language_code or "unknown"
            for recognizer in self._recognizers:
                recognizer_name = type(recognizer).__name__
                for raw in recognizer.recognize(chunk.text):
                    start_offset = raw.get("start_offset")
                    end_offset = raw.get("end_offset")
                    if start_offset is None or end_offset is None:
                        start_offset, end_offset = _text_offsets(chunk.text, raw["raw_text"])
                    mentions.append(
                        SpatialMentionDto(
                            chunk_id=chunk.chunk_id,
                            raw_text=raw["raw_text"],
                            normalized_location=raw["normalized_location"],
                            location_type=raw["location_type"],
                            confidence=self._scorer.score(raw),
                            language_code=language_code,
                            recognizer_name=recognizer_name,
                            start_offset=start_offset,
                            end_offset=end_offset,
                            site_id=raw.get("site_id"),
                            metadata=dict(raw.get("metadata") or {}),
                        )
                    )
        self._spatial_repository.replace_for_job(
            ctx.job_id, [spatial_dto_to_orm(ctx, mention) for mention in mentions]
        )
        trace = {
            "chunks_processed": len(chunks),
            "spatial_mentions_created": len(mentions),
        }
        return SpatialExtractionResult(mentions=tuple(mentions), trace=trace)


__all__ = ["SpatialExtractionService"]
