from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import TemporalMentionDto
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.mapper.discovery_mapper import temporal_dto_to_orm
from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
from apps.kb.kb_discovery.temporal.DateRecognizer import DateRecognizer
from apps.kb.kb_discovery.temporal.DateRangeRecognizer import DateRangeRecognizer
from apps.kb.kb_discovery.temporal.DeadlineRecognizer import DeadlineRecognizer
from apps.kb.kb_discovery.temporal.RecurrenceRecognizer import RecurrenceRecognizer
from apps.kb.kb_discovery.temporal.RelativeDateResolver import RelativeDateResolver
from apps.kb.kb_discovery.temporal.TemporalContextScorer import TemporalContextScorer


class TemporalExtractionService:
    def __init__(self, temporal_repository: TemporalRepository) -> None:
        self._temporal_repository = temporal_repository
        self._recognizers = [
            DateRecognizer(),
            DateRangeRecognizer(),
            RelativeDateResolver(),
            DeadlineRecognizer(),
            RecurrenceRecognizer(),
        ]
        self._scorer = TemporalContextScorer()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> list[TemporalMentionDto]:
        mentions: list[TemporalMentionDto] = []
        for chunk in chunks:
            for recognizer in self._recognizers:
                for mention in recognizer.recognize(chunk):
                    mentions.append(
                        TemporalMentionDto(
                            chunk_id=chunk.chunk_id,
                            raw_text=mention["raw_text"],
                            normalized_start=mention.get("normalized_start"),
                            normalized_end=mention.get("normalized_end"),
                            temporal_type=mention["temporal_type"],
                            confidence=self._scorer.score(mention),
                        )
                    )
        self._temporal_repository.replace_for_job(
            ctx.job_id, [temporal_dto_to_orm(ctx, mention) for mention in mentions]
        )
        return mentions


__all__ = ["TemporalExtractionService"]
