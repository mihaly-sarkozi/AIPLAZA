from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class ClaimInterpretationSupportMixin:
    def _detect_assertion_mode(text: str) -> str:
        return ClaimPayloadBuilder.detect_assertion_mode(text)

    @staticmethod
    def _detect_time_framing(text: str, *, assertion_mode: str) -> tuple[str, str | None]:
        return ClaimPayloadBuilder.detect_time_framing(text, assertion_mode=assertion_mode)

    @staticmethod
    def _detect_space_framing(text: str, mentions: list[Mention]) -> tuple[str, str | None]:
        return ClaimPayloadBuilder.detect_space_framing(text, mentions)

    @staticmethod
    def _detect_claim_type(text: str, *, assertion_mode: str, mentions: list[Mention]) -> str:
        return ClaimPayloadBuilder.detect_claim_type(text, assertion_mode=assertion_mode, mentions=mentions)

    @staticmethod
    def _mention_patterns() -> list[tuple[str, str]]:
        return MentionResolutionService.mention_patterns()

    def _build_mentions_for_sentence(self, sentence: Sentence) -> list[Mention]:
        return self._mention_resolution_service.build_mentions_for_sentence(sentence)

    @staticmethod
    def _align_extracted_mentions_to_sentence(sentence: Sentence, mentions: list[Mention]) -> list[Mention]:
        return MentionResolutionService.align_extracted_mentions_to_sentence(sentence, mentions)

    @staticmethod
    def _merge_sentence_mentions(extracted_mentions: list[Mention], heuristic_mentions: list[Mention]) -> list[Mention]:
        return MentionResolutionService.merge_sentence_mentions(extracted_mentions, heuristic_mentions)

    @staticmethod
    def _is_mention_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_MENTION", False)
            or getattr(settings, "debug_mention", False)
            or sentence.metadata.get("mention_debug")
            or sentence.metadata.get("debug_mentions")
            or getattr(document, "metadata", {}).get("mention_debug")
            or getattr(source, "metadata", {}).get("mention_debug")
        )

    @staticmethod
    def _is_claim_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_CLAIM", False)
            or getattr(settings, "debug_claim", False)
            or sentence.metadata.get("claim_debug")
            or sentence.metadata.get("debug_claims")
            or getattr(document, "metadata", {}).get("claim_debug")
            or getattr(source, "metadata", {}).get("claim_debug")
        )

    @staticmethod
    def _is_space_time_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_SPACE_TIME", False)
            or getattr(settings, "debug_space_time", False)
            or sentence.metadata.get("space_time_debug")
            or sentence.metadata.get("debug_space_time")
            or getattr(document, "metadata", {}).get("space_time_debug")
            or getattr(source, "metadata", {}).get("space_time_debug")
        )

    @staticmethod
    def _claim_extractor_version() -> str:
        version = str(getattr(settings, "CLAIM_EXTRACTOR_VERSION", "v1") or "v1").strip().lower()
        return "v1" if version != "v1" else version

    @staticmethod
    def _resolve_sentence_language(
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> str:
        source_language = None
        if source is not None and isinstance(source.metadata, dict):
            source_language = source.metadata.get("language") or source.metadata.get("language_tag")
        preferred_language = (
            sentence.metadata.get("language")
            or sentence.metadata.get("language_tag")
            or getattr(document, "language", None)
            or source_language
        )
        return detect_language(sentence.text_content, preferred_language=preferred_language) or resolve_language(
            text=sentence.text_content,
            language=preferred_language,
        )

    def _build_sentence_mentions(
        self,
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> list[Mention]:
        language = self._resolve_sentence_language(sentence, source=source, document=document)
        sentence_mentions = self._mention_resolution_service.build_sentence_mentions(sentence, language=language)
        logger.debug(
            "[MENTION PIPELINE]\nsentence_id=%s\nmention_count=%s",
            sentence.id,
            len(sentence_mentions),
        )
        if self._is_mention_debug_enabled(source=source, document=document, sentence=sentence):
            debug_print_mentions(sentence, sentence_mentions, language=language)
        return sentence_mentions

    def _build_space_time_frames_for_claims(
        self,
        *,
        sentence: Sentence,
        claims: list[Claim],
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[list[Claim], list[SpaceTimeFrame]]:
        updated_claims: list[Claim] = []
        frames: list[SpaceTimeFrame] = []
        for claim in claims:
            updated_claim, frame = self.build_and_attach_space_time_frame(
                claim=claim,
                sentence=sentence,
                language=language,
                source=source,
                document=document,
                emit_logs=emit_logs,
            )
            updated_claims.append(updated_claim)
            frames.append(frame)
        return updated_claims, frames

    def build_and_attach_space_time_frame(
        self,
        *,
        claim: Claim,
        sentence: Sentence,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[Claim, SpaceTimeFrame]:
        frame = self._space_time_extractor_v1.extract(claim, sentence, language=language)
        if claim.space_time_frame_id:
            frame = replace(frame, id=claim.space_time_frame_id)
        updated_claim = replace(
            claim,
            space_time_frame_id=frame.frame_id,
            time_mode=frame.time_mode,
            time_label=frame.time_value,
            space_mode=frame.space_mode,
            space_label=frame.space_value,
            metadata={
                **dict(claim.metadata or {}),
                "space_time_frame_id": frame.frame_id,
                "space_time_language": frame.language,
                "space_time_frame_time_mode": frame.time_mode,
                "space_time_frame_space_mode": frame.space_mode,
                "space_time_frame_confidence": frame.overall_confidence,
            },
        )
        if emit_logs:
            logger.debug(
                "[SPACE-TIME PIPELINE]\nsentence_id=%s\nclaim_id=%s\nframe_id=%s\ntime_mode=%s\nspace_mode=%s\nconfidence=%s",
                sentence.id,
                updated_claim.claim_id,
                frame.frame_id,
                frame.time_mode,
                frame.space_mode,
                frame.overall_confidence,
            )
            if self._is_space_time_debug_enabled(source=source, document=document, sentence=sentence):
                SpaceTimeExtractorV1.debug_print(updated_claim, frame)
        return updated_claim, frame

    def _build_sentence_claim_payload(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        *,
        source: Source | None = None,
        document: Document | None = None,
        defer_space_time: bool = False,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        return self._claim_payload_builder.build_sentence_claim_payload(
            sentence=sentence,
            mentions=mentions,
            source=source,
            document=document,
            defer_space_time=defer_space_time,
        )

    def _finalize_sentence_after_subject_context(
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
        return self._claim_payload_builder.finalize_sentence_after_subject_context(
            sentence=sentence,
            mentions=mentions,
            interpretation=interpretation,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )

    def get_ingest_run_trace(
        self,
        run_id: str,
        *,
        log_level: str | None = "FULL_TRACE",
        debug: bool = False,
    ) -> dict[str, Any] | None:
        return self._trace_service.build_trace(run_id, log_level=log_level, debug=debug)

    def _log_ingest_trace_summary(self, run_id: str) -> None:
        trace = self.get_ingest_run_trace(run_id)
        if trace is None:
            return
        summary = trace.get("summary") or {}
        logger.debug(
            "[KNOWLEDGE TRACE SUMMARY]\nrun_id=%s\nsource_id=%s\nlanguage=%s\nsentence_count=%s\nmention_count=%s\nclaim_count=%s\nspace_time_frame_count=%s\nlocal_entity_cluster_count=%s\nlocal_entity_count=%s\nlow_coherence_local_entity_count=%s\nunknown_entity_type_count=%s",
            trace["run_id"],
            trace.get("source_id"),
            trace.get("language", "unknown"),
            summary.get("sentence_count", 0),
            summary.get("mention_count", 0),
            summary.get("claim_count", 0),
            summary.get("space_time_frame_count", 0),
            summary.get("local_entity_cluster_count", 0),
            summary.get("local_entity_count", 0),
            summary.get("low_coherence_local_entity_count", 0),
            summary.get("unknown_entity_type_count", 0),
        )

    @staticmethod
    def _detect_predicate(text: str) -> tuple[str, int]:
        return ClaimPayloadBuilder.detect_predicate(text)

    def _build_claim_for_sentence(self, sentence: Sentence, mentions: list[Mention]) -> tuple[SentenceInterpretation, list[Claim]]:
        return self._claim_payload_builder.build_claim_for_sentence(sentence, mentions)

    def _build_sentence_interpretation_payload(self, sentence: Sentence) -> dict[str, Any]:
        return self._claim_payload_builder.build_sentence_interpretation_payload(sentence)

    def _score_information_value(
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


__all__ = ["ClaimInterpretationSupportMixin"]
