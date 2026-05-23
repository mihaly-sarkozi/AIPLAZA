from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class SentenceCompatibilityMixin:
    @staticmethod
    def _normalize_parser_text(value: str | None) -> str:
        return SentenceUnitBuilder.normalize_parser_text(value)

    @staticmethod
    def _describe_empty_extraction(metadata: dict[str, Any] | None) -> str:
        info = dict(metadata or {})
        if info.get("source_format") == "pdf" and info.get("no_extractable_text"):
            page_count = int(info.get("page_count") or 0)
            producer = str(info.get("pdf_producer") or "").strip()
            creator = str(info.get("pdf_creator") or "").strip()
            title = str(info.get("pdf_title") or "").strip()
            details: list[str] = []
            if page_count > 0:
                details.append(f"{page_count} oldalas PDF")
            if producer:
                details.append(f"producer: {producer}")
            if creator:
                details.append(f"creator: {creator}")
            if title:
                details.append(f"cím: {title}")
            detail_text = f" ({'; '.join(details)})" if details else ""
            return (
                "A PDF-ből nem nyerhető ki szöveg, mert nem tartalmaz kiolvasható szövegréteget"
                f"{detail_text}. Valószínűleg képalapú vagy szkennelt PDF, ezért OCR szükséges."
            )
        return "A forrásból nem nyerhető ki feldolgozható szöveg."

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        return SentenceUnitBuilder.split_paragraphs(text)

    @staticmethod
    def _normalize_sentence_candidate_text(value: str) -> str:
        return SentenceUnitBuilder.normalize_sentence_candidate_text(value)

    @staticmethod
    def _sentence_word_count(value: str) -> int:
        return SentenceUnitBuilder.sentence_word_count(value)

    @staticmethod
    def _looks_like_noise_sentence_candidate(text: str) -> bool:
        return SentenceUnitBuilder.looks_like_noise_sentence_candidate(text)

    @staticmethod
    def _next_token(text: str, start_idx: int) -> str:
        return SentenceUnitBuilder.next_token(text, start_idx)

    @staticmethod
    def _token_with_period_before(text: str, end_idx: int) -> str:
        return SentenceUnitBuilder.token_with_period_before(text, end_idx)

    @staticmethod
    def _is_abbreviation_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_abbreviation_boundary(text, end_idx)

    @staticmethod
    def _is_date_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_date_boundary(text, end_idx)

    @staticmethod
    def _is_dotted_abbreviation_continuation(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_dotted_abbreviation_continuation(text, end_idx)

    @staticmethod
    def _is_legal_reference_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_legal_reference_boundary(text, end_idx)

    @staticmethod
    def _is_numeric_list_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_numeric_list_boundary(text, end_idx)

    @staticmethod
    def _is_marker_only_fragment(text: str, start_idx: int, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_marker_only_fragment(text, start_idx, end_idx)

    @staticmethod
    def _split_heading_sentence_candidates(text: str) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_heading_sentence_candidates(text)

    @staticmethod
    def _is_parenthesized_list_marker_start(text: str, marker_start: int) -> bool:
        return SentenceUnitBuilder.is_parenthesized_list_marker_start(text, marker_start)

    @staticmethod
    def _is_inline_heading_marker_start(text: str, marker_start: int, marker_end: int) -> bool:
        return SentenceUnitBuilder.is_inline_heading_marker_start(text, marker_start, marker_end)

    @staticmethod
    def _build_sentence_candidate(
        text: str,
        start: int,
        end: int,
        *,
        confidence: float,
        split_reason: str,
        block_type: str | None = None,
    ) -> SentenceCandidate | None:
        return SentenceUnitBuilder.build_sentence_candidate(
            text,
            start,
            end,
            confidence=confidence,
            split_reason=split_reason,
            block_type=block_type,
        )

    @staticmethod
    def _long_segment_break_index(text: str, start: int, end: int) -> int | None:
        return SentenceUnitBuilder.long_segment_break_index(text, start, end)

    @staticmethod
    def _split_long_candidate(candidate: SentenceCandidate) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_long_candidate(candidate)

    @staticmethod
    def _split_sentence_candidates(text: str, *, block_type: str | None = None) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_sentence_candidates(text, block_type=block_type)

    @staticmethod
    def _split_sentences(text: str, *, block_type: str | None = None) -> list[str]:
        return SentenceUnitBuilder.split_sentences(text, block_type=block_type)

    @staticmethod
    def _build_table_sentence_units(paragraph_text: str, paragraph_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        return SentenceUnitBuilder.build_table_sentence_units(paragraph_text, paragraph_metadata)

    @classmethod
    def _is_strong_sentence_candidate(cls, candidate: SentenceCandidate) -> bool:
        return SentenceUnitBuilder.is_strong_sentence_candidate(candidate)

    @classmethod
    def _build_claim_refinement_budget(cls, total_blocks: int) -> int:
        return InformationValueScorer.build_claim_refinement_budget(total_blocks)

    @classmethod
    def _count_claim_refinement_signals(cls, text: str) -> dict[str, int]:
        return InformationValueScorer.count_claim_refinement_signals(text)

    @classmethod
    def _should_attempt_claim_refinement(
        cls,
        candidate: SentenceCandidate,
        *,
        block_type: str,
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, int]]:
        return InformationValueScorer.should_attempt_claim_refinement(
            candidate,
            block_type=block_type,
            refinement_state=refinement_state,
        )

    def _sync_sentence_builder_compat(self) -> None:
        self._sentence_unit_builder._claim_fine_splitter = self._claim_fine_splitter
        self._sentence_unit_builder.is_strong_sentence_candidate = self._is_strong_sentence_candidate
        self._sentence_unit_builder.should_attempt_claim_refinement = self._should_attempt_claim_refinement

    @staticmethod
    def _language_tag_from_metadata(metadata: dict[str, Any]) -> str | None:
        return SentenceUnitBuilder.language_tag_from_metadata(metadata)

    @staticmethod
    def _sentence_unit_from_candidate(candidate: SentenceCandidate, *, strong_split: bool) -> dict[str, Any]:
        return SentenceUnitBuilder.sentence_unit_from_candidate(candidate, strong_split=strong_split)

    def _refine_candidate_with_claim_splitter(
        self,
        paragraph_text: str,
        candidate: SentenceCandidate,
        *,
        paragraph_metadata: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        self._sync_sentence_builder_compat()
        return self._sentence_unit_builder.refine_candidate_with_claim_splitter(
            paragraph_text,
            candidate,
            paragraph_metadata=paragraph_metadata,
        )

    def _build_sentence_units_for_paragraph(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self._sync_sentence_builder_compat()
        return self._sentence_unit_builder.build_sentence_units_for_paragraph(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )

    def _build_sentence_units_for_paragraph_with_diagnostics(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self._sync_sentence_builder_compat()
        return self._sentence_unit_builder.build_sentence_units_for_paragraph_with_diagnostics(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )



__all__ = ["SentenceCompatibilityMixin"]
