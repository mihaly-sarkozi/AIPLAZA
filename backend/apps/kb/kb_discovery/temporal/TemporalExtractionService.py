from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import TemporalExtractionResult, TemporalMentionDto
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.mapper.discovery_mapper import temporal_dto_to_orm
from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
from apps.kb.kb_discovery.temporal.DateRecognizer import DateRecognizer
from apps.kb.kb_discovery.temporal.DateRangeRecognizer import DateRangeRecognizer
from apps.kb.kb_discovery.temporal.DeadlineRecognizer import DeadlineRecognizer
from apps.kb.kb_discovery.temporal.RecurrenceRecognizer import RecurrenceRecognizer
from apps.kb.kb_discovery.temporal.RelativeDateResolver import RelativeDateResolver
from apps.kb.kb_discovery.temporal.TemporalContextScorer import TemporalContextScorer


def _text_offsets(text: str, raw_text: str) -> tuple[int | None, int | None]:
    index = text.find(raw_text)
    if index < 0:
        return None, None
    return index, index + len(raw_text)


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

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> TemporalExtractionResult:
        mentions: list[TemporalMentionDto] = []
        for chunk in chunks:
            language_code = chunk.language_code or ctx.language_code or "unknown"
            for recognizer in self._recognizers:
                recognizer_name = type(recognizer).__name__
                for mention in recognizer.recognize(chunk):
                    start_offset = mention.get("start_offset")
                    end_offset = mention.get("end_offset")
                    if start_offset is None or end_offset is None:
                        start_offset, end_offset = _text_offsets(chunk.text, mention["raw_text"])
                    mentions.append(
                        TemporalMentionDto(
                            chunk_id=chunk.chunk_id,
                            raw_text=mention["raw_text"],
                            normalized_start=mention.get("normalized_start"),
                            normalized_end=mention.get("normalized_end"),
                            temporal_type=mention["temporal_type"],
                            confidence=self._scorer.score(mention),
                            language_code=language_code,
                            recognizer_name=recognizer_name,
                            start_offset=start_offset,
                            end_offset=end_offset,
                            metadata=dict(mention.get("metadata") or {}),
                        )
                    )
        self._temporal_repository.replace_for_job(
            ctx.job_id, [temporal_dto_to_orm(ctx, mention) for mention in mentions]
        )
        trace = {
            "chunks_processed": len(chunks),
            "temporal_mentions_created": len(mentions),
        }
        return TemporalExtractionResult(mentions=tuple(mentions), trace=trace)


__all__ = ["TemporalExtractionService"]
