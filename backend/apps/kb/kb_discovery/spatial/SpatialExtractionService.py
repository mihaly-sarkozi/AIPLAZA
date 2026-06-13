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
            for recognizer in self._recognizers:
                for raw in recognizer.recognize(chunk.text):
                    mentions.append(
                        SpatialMentionDto(
                            chunk_id=chunk.chunk_id,
                            raw_text=raw["raw_text"],
                            normalized_location=raw["normalized_location"],
                            location_type=raw["location_type"],
                            confidence=self._scorer.score(raw),
                            site_id=raw.get("site_id"),
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
