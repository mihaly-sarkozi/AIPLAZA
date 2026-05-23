# backend/apps/knowledge/service/claim_payload_builder.py
# Builds baseline and v1 sentence claim payloads for document interpretation.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import logging
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.claim_extraction_pipeline import run_v1_sentence_claim_pipeline
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_frame_detector import ClaimFrameDetector
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.claim_typing import debug_claim_type
from apps.knowledge.service.information_value_scorer import InformationValueScorer
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1

logger = logging.getLogger(__name__)


class ClaimPayloadBuilder:
    def __init__(
        self,
        *,
        claim_extractor: ClaimExtractorV1,
        quality_gate: ClaimQualityGate,
        information_value_scorer: InformationValueScorer,
        resolve_sentence_language: Callable[..., str],
        build_sentence_mentions: Callable[..., list[Mention]],
        build_space_time_frames_for_claims: Callable[..., tuple[list[Claim], list[SpaceTimeFrame]]],
        is_claim_debug_enabled: Callable[..., bool],
    ) -> None:
        self._claim_extractor = claim_extractor
        self._quality_gate = quality_gate
        self._information_value_scorer = information_value_scorer
        self._resolve_sentence_language = resolve_sentence_language
        self._build_sentence_mentions = build_sentence_mentions
        self._build_space_time_frames_for_claims = build_space_time_frames_for_claims
        self._is_claim_debug_enabled = is_claim_debug_enabled

    @staticmethod
    def detect_assertion_mode(text: str) -> str:
        return ClaimFrameDetector.detect_assertion_mode(text)

    @staticmethod
    def detect_time_framing(text: str, *, assertion_mode: str) -> tuple[str, str | None]:
        return ClaimFrameDetector.detect_time_framing(text, assertion_mode=assertion_mode)

    @staticmethod
    def detect_space_framing(text: str, mentions: list[Mention]) -> tuple[str, str | None]:
        return ClaimFrameDetector.detect_space_framing(text, mentions)

    @staticmethod
    def detect_claim_type(text: str, *, assertion_mode: str, mentions: list[Mention]) -> str:
        return ClaimFrameDetector.detect_claim_type(text, assertion_mode=assertion_mode, mentions=mentions)

    @staticmethod
    def detect_predicate(text: str) -> tuple[str, int]:
        return ClaimFrameDetector.detect_predicate(text)

    def build_claim_for_sentence(self, sentence: Sentence, mentions: list[Mention]) -> tuple[SentenceInterpretation, list[Claim]]:
        text = sentence.text_content.strip()
        block_type = str(sentence.metadata.get("block_type") or "")
        header_context_text = str(sentence.metadata.get("header_context_text") or "").strip()
        metadata_kind = str(sentence.metadata.get("metadata_kind") or "").strip()
        if block_type in {"metadata", "noise"}:
            interpretation = SentenceInterpretation(
                tenant=sentence.tenant,
                corpus_uuid=sentence.corpus_uuid,
                source_id=sentence.source_id,
                document_id=sentence.document_id,
                sentence_id=sentence.id,
                sentence_text=text,
                claim_summary=text,
                assertion_mode="ignored_structure",
                claim_type=metadata_kind or block_type,
                time_mode="unknown",
                time_label=None,
                space_mode="unknown",
                space_label=None,
                confidence=0.2,
                metadata={
                    "sentence_order": sentence.order_index,
                    "block_type": block_type,
                    "metadata_kind": metadata_kind or None,
                    "page_number": sentence.metadata.get("page_number"),
                    "interpretation_skipped": True,
                    "skip_reason": metadata_kind or block_type,
                },
            )
            return self._with_information_value(sentence=sentence, mentions=[], claim=None, interpretation=interpretation), []
        if block_type == "heading":
            interpretation = SentenceInterpretation(
                tenant=sentence.tenant,
                corpus_uuid=sentence.corpus_uuid,
                source_id=sentence.source_id,
                document_id=sentence.document_id,
                sentence_id=sentence.id,
                sentence_text=text,
                claim_summary=text,
                assertion_mode="context_header",
                claim_type="context_header",
                time_mode="location_independent",
                time_label=None,
                space_mode="location_independent",
                space_label=None,
                confidence=0.82,
                metadata={
                    "sentence_order": sentence.order_index,
                    "block_type": block_type,
                    "page_number": sentence.metadata.get("page_number"),
                    "header_scope": "section_context",
                    "is_contextual_header": True,
                },
            )
            return self._with_information_value(sentence=sentence, mentions=mentions, claim=None, interpretation=interpretation), []

        assertion_mode = self.detect_assertion_mode(text)
        time_mode, time_label = self.detect_time_framing(text, assertion_mode=assertion_mode)
        space_mode, space_label = self.detect_space_framing(text, mentions)
        claim_type = self.detect_claim_type(text, assertion_mode=assertion_mode, mentions=mentions)
        predicate_text, predicate_idx = self.detect_predicate(text)
        subject_text = ""
        object_text: str | None = None

        if mentions:
            subject_candidates = [item for item in mentions if item.mention_type in {"person", "organization", "role", "system"}]
            if subject_candidates:
                subject_text = subject_candidates[0].text_content
        if not subject_text and predicate_idx > 0:
            subject_text = text[:predicate_idx].strip(" ,;:-")
        if not subject_text:
            subject_text = text.split()[0] if text.split() else text
        predicate_end = predicate_idx + len(predicate_text)
        if predicate_end < len(text):
            object_text = text[predicate_end:].strip(" ,;:-") or None
        if not object_text and len(text.split()) > 2:
            object_text = " ".join(text.split()[2:]) or None

        summary = " ".join(part for part in [subject_text, predicate_text, object_text] if part).strip()
        interpretation = SentenceInterpretation(
            tenant=sentence.tenant,
            corpus_uuid=sentence.corpus_uuid,
            source_id=sentence.source_id,
            document_id=sentence.document_id,
            sentence_id=sentence.id,
            sentence_text=text,
            claim_summary=summary or text,
            assertion_mode=assertion_mode,
            claim_type=claim_type,
            time_mode=time_mode,
            time_label=time_label,
            space_mode=space_mode,
            space_label=space_label,
            confidence=0.72,
            metadata={
                "sentence_order": sentence.order_index,
                "block_type": block_type,
                "page_number": sentence.metadata.get("page_number"),
                "header_context_text": header_context_text or None,
                "header_context_sentence_id": sentence.metadata.get("header_context_sentence_id"),
                "header_context_paragraph_id": sentence.metadata.get("header_context_paragraph_id"),
            },
        )
        claim = Claim(
            tenant=sentence.tenant,
            corpus_uuid=sentence.corpus_uuid,
            source_id=sentence.source_id,
            document_id=sentence.document_id,
            sentence_id=sentence.id,
            subject_text=subject_text,
            predicate_text=predicate_text,
            object_text=object_text,
            claim_type=claim_type,
            assertion_mode=assertion_mode,
            time_mode=time_mode,
            time_label=time_label,
            space_mode=space_mode,
            space_label=space_label,
            confidence=0.69,
            metadata={"mention_count": len(mentions)},
        )
        return self._with_information_value(sentence=sentence, mentions=mentions, claim=claim, interpretation=interpretation), [claim]

    def build_sentence_claim_payload(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        *,
        source: Source | None = None,
        document: Document | None = None,
        defer_space_time: bool = False,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        baseline_interpretation, _baseline_claims = self.build_claim_for_sentence(sentence, mentions)
        language = self._resolve_sentence_language(sentence, source=source, document=document)
        claims, claim_quality = run_v1_sentence_claim_pipeline(
            sentence=sentence,
            mentions=mentions,
            resolved_language=language,
            extractor=self._claim_extractor,
            quality_gate=self._quality_gate,
        )
        logger.debug(
            "[CLAIM QUALITY GATE]\nsentence_id=%s\nraw_claim_count=%s\naccepted_claim_count=%s\nrejected_claim_count=%s\nskipped=%s\nsentence_reason=%s",
            sentence.id,
            int(claim_quality.get("generated_claim_count") or 0),
            len(claims),
            int(claim_quality.get("rejected_claim_count") or 0),
            bool(claim_quality.get("skipped")),
            claim_quality.get("sentence_reason"),
        )
        for rejected in list(claim_quality.get("rejected_claims") or []):
            logger.debug(
                "[CLAIM REJECTED]\nsentence_id=%s\nreason=%s\nextraction_pattern=%s\nextraction_language=%s\nsubject=%s\npredicate=%s\nobject=%s",
                sentence.id,
                rejected.get("reason"),
                rejected.get("extraction_pattern") or rejected.get("pattern_name"),
                rejected.get("extraction_language"),
                rejected.get("subject_text"),
                rejected.get("predicate"),
                rejected.get("object_text"),
            )
        if self._is_claim_debug_enabled(source=source, document=document, sentence=sentence):
            ClaimExtractorV1.debug_print(sentence, claims, language=language)
            for claim in claims:
                debug_claim_type(claim)

        if not claims:
            logger.debug(
                "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
                sentence.id,
                len(mentions),
                0,
            )
            return (
                replace(
                    baseline_interpretation,
                    metadata={
                        **baseline_interpretation.metadata,
                        "claim_extractor_version": "v1",
                        "space_time_frame_status": "empty",
                        "language": language,
                        "quality_gate": claim_quality,
                    },
                ),
                [],
                [],
            )

        if defer_space_time:
            primary_claim = claims[0]
            interpretation = replace(
                baseline_interpretation,
                claim_summary=primary_claim.claim_text or baseline_interpretation.claim_summary,
                claim_type=primary_claim.claim_type,
                confidence=max(float(baseline_interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
                metadata={
                    **baseline_interpretation.metadata,
                    "claim_extractor_version": "v1",
                    "space_time_frame_status": "pending",
                    "language": language,
                    "quality_gate": claim_quality,
                },
            )
            return interpretation, claims, []

        claims, space_time_frames = self._build_space_time_frames_for_claims(
            sentence=sentence,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )
        primary_claim = claims[0]
        interpretation = replace(
            baseline_interpretation,
            claim_summary=primary_claim.claim_text or baseline_interpretation.claim_summary,
            claim_type=primary_claim.claim_type,
            confidence=max(float(baseline_interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
            metadata={
                **baseline_interpretation.metadata,
                "claim_extractor_version": "v1",
                "space_time_frame_status": "created" if space_time_frames else "empty",
                "space_time_frame_ids": [item.frame_id for item in space_time_frames],
                "language": language,
                "quality_gate": claim_quality,
            },
        )
        interpretation = self._with_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=primary_claim,
            interpretation=interpretation,
        )
        logger.debug(
            "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
            sentence.id,
            len(mentions),
            len(claims),
        )
        return interpretation, claims, space_time_frames

    def finalize_sentence_after_subject_context(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        interpretation: SentenceInterpretation,
        claims: list[Claim],
        *,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        if not claims:
            return (
                replace(
                    interpretation,
                    metadata={
                        **interpretation.metadata,
                        "space_time_frame_status": "empty",
                    },
                ),
                claims,
                [],
            )

        claims, space_time_frames = self._build_space_time_frames_for_claims(
            sentence=sentence,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )
        primary_claim = claims[0]
        interpretation = replace(
            interpretation,
            claim_summary=primary_claim.claim_text or interpretation.claim_summary,
            claim_type=primary_claim.claim_type,
            confidence=max(float(interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
            metadata={
                **interpretation.metadata,
                "space_time_frame_status": "created" if space_time_frames else "empty",
                "space_time_frame_ids": [item.frame_id for item in space_time_frames],
                "language": language,
            },
        )
        interpretation = self._with_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=primary_claim,
            interpretation=interpretation,
        )
        logger.debug(
            "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
            sentence.id,
            len(mentions),
            len(claims),
        )
        return interpretation, claims, space_time_frames

    def build_sentence_interpretation_payload(self, sentence: Sentence) -> dict[str, Any]:
        mentions = self._build_sentence_mentions(sentence)
        interpretation, claims, _ = self.build_sentence_claim_payload(sentence, mentions, defer_space_time=True)
        language = str(interpretation.metadata.get("language") or self._resolve_sentence_language(sentence))
        resolved = SubjectContextResolverV1().resolve_claims(
            [
                {
                    "sentence_id": sentence.id,
                    "order_index": sentence.order_index,
                    "text": sentence.text_content,
                    "language": language,
                    "mentions": mentions,
                    "claims": claims,
                }
            ]
        )
        claims = list(resolved[0].get("claims") or [])
        interpretation, claims, frames = self.finalize_sentence_after_subject_context(
            sentence,
            mentions,
            interpretation,
            claims,
            language=language,
            source=None,
            document=None,
        )
        return {
            "interpretation": interpretation,
            "mentions": mentions,
            "claims": claims,
            "space_time_frames": frames,
        }

    def score_information_value(
        self,
        *,
        sentence: Sentence,
        mentions: list[Mention],
        claim: Claim | None,
        interpretation: SentenceInterpretation,
    ) -> tuple[float, str, str]:
        return self._information_value_scorer.score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=claim,
            interpretation=interpretation,
        )

    def _with_information_value(
        self,
        *,
        sentence: Sentence,
        mentions: list[Mention],
        claim: Claim | None,
        interpretation: SentenceInterpretation,
    ) -> SentenceInterpretation:
        score, status, reason = self.score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=claim,
            interpretation=interpretation,
        )
        return replace(
            interpretation,
            information_value_score=score,
            information_value_status=status,
            information_value_reason=reason,
            metadata={
                **interpretation.metadata,
                "information_value_score": score,
                "information_value_status": status,
                "information_value_reason": reason,
            },
        )


__all__ = ["ClaimPayloadBuilder"]
