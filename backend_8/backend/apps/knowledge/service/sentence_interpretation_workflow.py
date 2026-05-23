from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.facade_helpers import empty_claim_quality_summary, merge_claim_quality_summary
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1


@dataclass(frozen=True)
class SentenceInterpretationWorkflowResult:
    mentions: list[Mention]
    interpretations: list[SentenceInterpretation]
    claims: list[Claim]
    space_time_frames: list[SpaceTimeFrame]
    quality_summary: dict[str, Any]


class SentenceInterpretationWorkflow:
    def __init__(
        self,
        *,
        build_sentence_mentions: Callable[..., list[Mention]],
        resolve_sentence_language: Callable[..., str],
        build_sentence_claim_payload: Callable[..., tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]],
        finalize_sentence_after_subject_context: Callable[..., tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]],
    ) -> None:
        self._build_sentence_mentions = build_sentence_mentions
        self._resolve_sentence_language = resolve_sentence_language
        self._build_sentence_claim_payload = build_sentence_claim_payload
        self._finalize_sentence_after_subject_context = finalize_sentence_after_subject_context

    def run(
        self,
        *,
        run_id: str,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> SentenceInterpretationWorkflowResult:
        mentions: list[Mention] = []
        quality_summary = empty_claim_quality_summary()
        staged: list[tuple[Sentence, list[Mention], SentenceInterpretation, str, list[Claim]]] = []
        for index, sentence in enumerate(sentences, start=1):
            sentence_mentions = self._build_sentence_mentions(sentence, source=source, document=document)
            sentence_language = self._resolve_sentence_language(sentence, source=source, document=document)
            sentence_interpretation, sentence_claims, _ = self._build_sentence_claim_payload(
                sentence,
                sentence_mentions,
                source=source,
                document=document,
                defer_space_time=True,
            )
            sentence_interpretation = replace(sentence_interpretation, interpretation_run_id=run_id)
            sentence_mentions = [replace(item, interpretation_run_id=run_id) for item in sentence_mentions]
            sentence_claims = [replace(item, interpretation_run_id=run_id) for item in sentence_claims]
            quality_summary = merge_claim_quality_summary(
                quality_summary,
                dict(sentence_interpretation.metadata.get("quality_gate") or {}),
            )
            staged.append((sentence, sentence_mentions, sentence_interpretation, sentence_language, sentence_claims))
            mentions.extend(sentence_mentions)
            self._emit_progress(progress_callback, run_id, index, len(sentences))

        resolved_by_sid = self._resolve_subject_context(staged)
        interpretations: list[SentenceInterpretation] = []
        claims: list[Claim] = []
        space_time_frames: list[SpaceTimeFrame] = []
        for sentence, sentence_mentions, sentence_interpretation, sentence_language, _ in staged:
            row = resolved_by_sid.get(str(sentence.id))
            sentence_claims = list((row or {}).get("claims") or [])
            interp_out, claims_out, frames_out = self._finalize_sentence_after_subject_context(
                sentence,
                sentence_mentions,
                sentence_interpretation,
                sentence_claims,
                language=sentence_language,
                source=source,
                document=document,
            )
            interpretations.append(interp_out)
            claims.extend(claims_out)
            space_time_frames.extend(frames_out)
        return SentenceInterpretationWorkflowResult(
            mentions=mentions,
            interpretations=interpretations,
            claims=claims,
            space_time_frames=space_time_frames,
            quality_summary=quality_summary,
        )

    @staticmethod
    def _emit_progress(
        progress_callback: Callable[[str, dict[str, Any]], None] | None,
        run_id: str,
        processed_sentences: int,
        total_sentences: int,
    ) -> None:
        if progress_callback is not None:
            progress_callback(
                "interpretation_progress",
                {
                    "interpretation_run_id": run_id,
                    "processed_sentences": processed_sentences,
                    "total_sentences": total_sentences,
                },
            )

    @staticmethod
    def _resolve_subject_context(
        staged: list[tuple[Sentence, list[Mention], SentenceInterpretation, str, list[Claim]]],
    ) -> dict[str, dict[str, Any]]:
        payload = [
            {
                "sentence_id": sentence.id,
                "order_index": sentence.order_index,
                "text": sentence.text_content,
                "language": language,
                "mentions": mentions,
                "claims": claims,
            }
            for sentence, mentions, _interp, language, claims in staged
        ]
        return {str(row.get("sentence_id") or ""): row for row in SubjectContextResolverV1().resolve_claims(payload)}


__all__ = ["SentenceInterpretationWorkflow", "SentenceInterpretationWorkflowResult"]
