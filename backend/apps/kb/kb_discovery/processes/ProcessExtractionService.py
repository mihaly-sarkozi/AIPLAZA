from __future__ import annotations

import re

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import ProcessExtractionResult, ProcessMentionDto
from apps.kb.kb_discovery.mapper.discovery_mapper import process_dto_to_orm
from apps.kb.kb_discovery.processes.ChecklistExtractor import ChecklistExtractor
from apps.kb.kb_discovery.processes.ProcessConfidenceScorer import ProcessConfidenceScorer
from apps.kb.kb_discovery.processes.ResponsibilityDetector import ResponsibilityDetector
from apps.kb.kb_discovery.processes.StepDetector import StepDetector
from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository


class ProcessExtractionService:
    _PROCESS_NAME = re.compile(
        r"(?:folyamat|process|eljárás|workflow)\s*:?\s*([\wÁÉÍÓÖŐÚÜŰáéíóöőúüű .-]+)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        process_repository: ProcessRepository,
        *,
        step_detector: StepDetector | None = None,
        checklist_extractor: ChecklistExtractor | None = None,
        responsibility_detector: ResponsibilityDetector | None = None,
        scorer: ProcessConfidenceScorer | None = None,
    ) -> None:
        self._process_repository = process_repository
        self._step_detector = step_detector or StepDetector()
        self._checklist = checklist_extractor or ChecklistExtractor()
        self._responsibility = responsibility_detector or ResponsibilityDetector()
        self._scorer = scorer or ProcessConfidenceScorer()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> ProcessExtractionResult:
        mentions: list[ProcessMentionDto] = []
        chunks_with_steps = 0

        for chunk in chunks:
            language_code = chunk.language_code or ctx.language_code or "unknown"
            process_name = self._detect_process_name(chunk.text)
            responsibilities = self._responsibility.detect(chunk.text)
            responsibility = responsibilities[0] if responsibilities else None

            steps = self._step_detector.detect(chunk.text)
            if steps:
                chunks_with_steps += 1
                confidence = self._scorer.score(len(steps))
                for step_order, step_text in steps:
                    mentions.append(
                        ProcessMentionDto(
                            chunk_id=chunk.chunk_id,
                            process_name=process_name,
                            step_text=step_text,
                            step_order=step_order,
                            responsibility=responsibility,
                            is_required=True,
                            is_optional=False,
                            confidence=confidence,
                            language_code=language_code,
                            recognizer_name="step_detector",
                        )
                    )

            checklist_items = self._checklist.extract(chunk.text)
            if checklist_items and not steps:
                chunks_with_steps += 1
                confidence = self._scorer.score(len(checklist_items))
                for index, item in enumerate(checklist_items, start=1):
                    mentions.append(
                        ProcessMentionDto(
                            chunk_id=chunk.chunk_id,
                            process_name=process_name,
                            step_text=item,
                            step_order=index,
                            responsibility=responsibility,
                            is_required=False,
                            is_optional=True,
                            confidence=confidence,
                            language_code=language_code,
                            recognizer_name="checklist_extractor",
                        )
                    )

        self._process_repository.replace_for_job(
            ctx.job_id,
            [process_dto_to_orm(ctx, mention) for mention in mentions],
        )
        trace = {
            "chunks_processed": len(chunks),
            "process_mentions_created": len(mentions),
            "chunks_with_steps": chunks_with_steps,
        }
        return ProcessExtractionResult(mentions=tuple(mentions), trace=trace)

    def _detect_process_name(self, text: str) -> str:
        match = self._PROCESS_NAME.search(text)
        if match:
            return match.group(1).strip()[:256]
        return "detected_process"


__all__ = ["ProcessExtractionService"]
