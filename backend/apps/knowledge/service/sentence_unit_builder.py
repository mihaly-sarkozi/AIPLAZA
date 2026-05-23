# backend/apps/knowledge/service/sentence_unit_builder.py
# Builds paragraph and sentence units from parser text. This component owns the
# former KnowledgeFacade sentence splitting and claim-refinement prefilter logic.

from __future__ import annotations

import re
from typing import Any

from apps.knowledge.service.claim_split import ClaimFineSplitter
from apps.knowledge.service.facade_helpers import SentenceCandidate, normalize_text_payload
from apps.knowledge.service.information_value_scorer import InformationValueScorer


class SentenceUnitBuilder:
    _SENTENCE_ABBREVIATIONS = {
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "ifj",
        "id",
        "stb",
        "kb",
        "pl",
        "ill",
        "old",
        "u",
        "vs",
        "etc",
        "eg",
        "ie",
        "usa",
    }
    _DATE_MONTH_PATTERN = (
        r"(?:jan(?:\.|uár)?|febr?(?:\.|uár)?|márc(?:\.|ius)?|ápr(?:\.|ilis)?|máj(?:\.|us)?|"
        r"jún(?:\.|ius)?|júl(?:\.|ius)?|aug(?:\.|usztus)?|szept?(?:\.|ember)?|"
        r"okt(?:\.|óber)?|nov(?:\.|ember)?|dec(?:\.|ember)?)"
    )
    _SENTENCE_DATE_PATTERNS = (
        re.compile(r"\b(?:19|20)\d{2}\.\s*(?:1[0-2]|0?[1-9])\.\s*(?:3[01]|[12]\d|0?[1-9])\.?"),
        re.compile(r"\b(?:3[01]|[12]\d|0?[1-9])\.\s*(?:1[0-2]|0?[1-9])\.\s*(?:19|20)\d{2}\.?"),
        re.compile(
            rf"\b(?:19|20)\d{{2}}\.\s*{_DATE_MONTH_PATTERN}\s+(?:0?[1-9]|[12]\d|3[01])\.?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:0?[1-9]|[12]\d|3[01])\.\s*{_DATE_MONTH_PATTERN}\s+(?:19|20)\d{{2}}\.?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:19|20)\d{{2}}\.\s*{_DATE_MONTH_PATTERN}\s+(?:0?[1-9]|[12]\d|3[01])\.\s+napján\b",
            flags=re.IGNORECASE,
        ),
    )
    _SECTION_MARKER_TOKEN = r"(?:\d+|[A-ZÁÉÍÓÖŐÚÜŰ]|[IVXLCDM]+)"
    _HEADING_MARKER_PATTERN = re.compile(rf"^(({_SECTION_MARKER_TOKEN}\.)+)\s+", flags=re.IGNORECASE)
    _INLINE_HEADING_MARKER_PATTERN = re.compile(rf"(?<!\w)((?:{_SECTION_MARKER_TOKEN}\.){{2,}})\s+", flags=re.IGNORECASE)
    _LIST_MARKER_PAREN_PATTERN = re.compile(r"(?<!\w)([a-záéíóöőúüű]\))\s+", flags=re.IGNORECASE)
    _NUMERIC_LIST_BOUNDARY_PATTERN = re.compile(r"\s+\d{1,2}\.\s+[A-ZÁÉÍÓÖŐÚÜŰ]")
    _CLAIM_STRONG_CONFIDENCE = 0.6

    def __init__(
        self,
        *,
        claim_fine_splitter: ClaimFineSplitter | None = None,
        information_value_scorer: InformationValueScorer | None = None,
        enable_claim_fine_split_during_parsing: bool = True,
    ) -> None:
        self._claim_fine_splitter = claim_fine_splitter
        self._information_value_scorer = information_value_scorer or InformationValueScorer()
        self._enable_claim_fine_split_during_parsing = bool(enable_claim_fine_split_during_parsing)

    @staticmethod
    def normalize_parser_text(value: str | None) -> str:
        text = normalize_text_payload(value)
        text = re.sub(r"(?<=\S)-\s*\n\s*(?=[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9])", "", text)
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    @staticmethod
    def split_paragraphs(text: str) -> list[str]:
        if not text.strip():
            return []
        chunks = [chunk.strip() for chunk in text.split("\n\n")]
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def normalize_sentence_candidate_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def sentence_word_count(value: str) -> int:
        return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE))

    @classmethod
    def looks_like_noise_sentence_candidate(cls, text: str) -> bool:
        normalized = cls.normalize_sentence_candidate_text(text)
        if not normalized:
            return True
        words = re.findall(r"\b\w+\b", normalized, flags=re.UNICODE)
        if len(words) < 3:
            return True
        if re.fullmatch(r"[\d\s.,;:!?()\"'\-_/\\]+", normalized):
            return True
        if re.fullmatch(r"[\W_]+", normalized, flags=re.UNICODE):
            return True
        return False

    @staticmethod
    def next_token(text: str, start_idx: int) -> str:
        match = re.search(r"[\"'„“”‘’(\[]*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+)", text[start_idx:])
        return match.group(1) if match else ""

    @staticmethod
    def token_with_period_before(text: str, end_idx: int) -> str:
        prefix = text[: end_idx + 1]
        match = re.search(
            r"([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű](?:\.[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])+\.?|[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]{1,10}\.)\W*$",
            prefix,
        )
        return match.group(1) if match else ""

    @classmethod
    def is_abbreviation_boundary(cls, text: str, end_idx: int) -> bool:
        dotted = cls.token_with_period_before(text, end_idx)
        if dotted:
            compact = dotted.replace(".", "").lower()
            if compact in cls._SENTENCE_ABBREVIATIONS:
                return True
            if re.fullmatch(r"(?:[A-Za-z]\.){2,}[A-Za-z]?", dotted):
                return True
        prev_token_match = re.search(r"([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+)\W*$", text[: end_idx + 1])
        prev_token = prev_token_match.group(1).lower() if prev_token_match else ""
        return prev_token in cls._SENTENCE_ABBREVIATIONS

    @classmethod
    def is_date_boundary(cls, text: str, end_idx: int) -> bool:
        window_start = max(0, end_idx - 32)
        window_end = min(len(text), end_idx + 32)
        snippet = text[window_start:window_end]
        local_idx = end_idx - window_start
        next_token = cls.next_token(text, end_idx + 1)
        for pattern in cls._SENTENCE_DATE_PATTERNS:
            for match in pattern.finditer(snippet):
                match_start, match_end = match.span()
                if not (match_start <= local_idx < match_end):
                    continue
                last_non_space = match_end - 1
                while last_non_space >= match_start and snippet[last_non_space].isspace():
                    last_non_space -= 1
                if local_idx < last_non_space:
                    return True
                return not (next_token and next_token[:1].isupper())
        return False

    @staticmethod
    def is_dotted_abbreviation_continuation(text: str, end_idx: int) -> bool:
        return end_idx + 1 < len(text) and text[end_idx + 1].isalpha()

    @staticmethod
    def is_legal_reference_boundary(text: str, end_idx: int) -> bool:
        return bool(re.match(r"\s*§", text[end_idx + 1 :]))

    @classmethod
    def is_numeric_list_boundary(cls, text: str, end_idx: int) -> bool:
        return bool(cls._NUMERIC_LIST_BOUNDARY_PATTERN.match(text[end_idx + 1 :]))

    @classmethod
    def is_marker_only_fragment(cls, text: str, start_idx: int, end_idx: int) -> bool:
        fragment = str(text[start_idx : end_idx + 1] or "").strip()
        if not fragment:
            return False
        return bool(re.fullmatch(rf"(?:{cls._SECTION_MARKER_TOKEN}\.)+", fragment, flags=re.IGNORECASE))

    @classmethod
    def split_heading_sentence_candidates(cls, text: str) -> list[SentenceCandidate]:
        marker_match = cls._HEADING_MARKER_PATTERN.match(text)
        if not marker_match:
            fallback_candidates = cls.split_sentence_candidates(text, block_type="heading_fragment")
            if len(fallback_candidates) <= 1:
                candidate = cls.build_sentence_candidate(
                    text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
                )
                return [candidate] if candidate else []
            result: list[SentenceCandidate] = []
            for candidate in fallback_candidates:
                mapped = cls.build_sentence_candidate(
                    text,
                    candidate.char_start_offset,
                    candidate.char_end_offset,
                    confidence=candidate.confidence,
                    split_reason="heading_sentence" if candidate.split_reason == "strong_punctuation" else candidate.split_reason,
                    block_type="heading",
                )
                if mapped:
                    result.append(mapped)
            return result
        body_start = marker_match.end()
        raw_body = text[body_start:]
        body_left_trim = len(raw_body) - len(raw_body.lstrip())
        body_offset = body_start + body_left_trim
        body_text = text[body_offset:]
        if not body_text:
            candidate = cls.build_sentence_candidate(
                text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
            )
            return [candidate] if candidate else []
        body_candidates = cls.split_sentence_candidates(body_text, block_type="heading_fragment")
        if len(body_candidates) <= 1:
            candidate = cls.build_sentence_candidate(
                text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
            )
            return [candidate] if candidate else []
        result: list[SentenceCandidate] = []
        for index, candidate in enumerate(body_candidates):
            mapped_start = 0 if index == 0 else body_offset + candidate.char_start_offset
            mapped_end = body_offset + candidate.char_end_offset
            mapped = cls.build_sentence_candidate(
                text,
                mapped_start,
                mapped_end,
                confidence=candidate.confidence,
                split_reason="heading_sentence" if index == 0 else candidate.split_reason,
                block_type="heading",
            )
            if mapped:
                result.append(mapped)
        return result

    @staticmethod
    def is_parenthesized_list_marker_start(text: str, marker_start: int) -> bool:
        prefix = text[:marker_start].rstrip()
        if not prefix:
            return False
        if prefix.endswith(("§", "bekezdés", "bek.", "pont", "alpont")):
            return False
        return True

    @classmethod
    def is_inline_heading_marker_start(cls, text: str, marker_start: int, marker_end: int) -> bool:
        prefix = text[:marker_start].rstrip()
        if not prefix:
            return False
        if prefix.endswith(("§", "bekezdés", "bek.", "pont", "alpont", "pontja", "fejezete")):
            return False
        if cls.sentence_word_count(prefix) < 2:
            return False
        next_token = cls.next_token(text, marker_end)
        if not next_token or not next_token[:1].isupper():
            return False
        return True

    @classmethod
    def build_sentence_candidate(
        cls,
        text: str,
        start: int,
        end: int,
        *,
        confidence: float,
        split_reason: str,
        block_type: str | None = None,
    ) -> SentenceCandidate | None:
        segment = text[start:end]
        if not segment:
            return None
        left_trim = len(segment) - len(segment.lstrip())
        right_trim = len(segment.rstrip())
        trimmed_start = start + left_trim
        trimmed_end = start + right_trim
        if trimmed_end <= trimmed_start:
            return None
        candidate_text = cls.normalize_sentence_candidate_text(text[trimmed_start:trimmed_end])
        if not candidate_text:
            return None
        if block_type not in {"heading", "list_item", "heading_fragment", "list_item_fragment"} and cls.looks_like_noise_sentence_candidate(candidate_text):
            return None
        return SentenceCandidate(
            text=candidate_text,
            confidence=max(0.0, min(0.99, round(confidence, 2))),
            split_reason=split_reason,
            char_start_offset=trimmed_start,
            char_end_offset=trimmed_end,
        )

    @staticmethod
    def long_segment_break_index(text: str, start: int, end: int) -> int | None:
        segment = text[start:end]
        words = list(re.finditer(r"\b\w+\b", segment, flags=re.UNICODE))
        if len(words) < 30:
            return None
        midpoint = len(segment) // 2
        conjunction_matches = list(
            re.finditer(r"\b(?:és|vagy|de|illetve|azonban|viszont)\b", segment, flags=re.IGNORECASE | re.UNICODE)
        )
        preferred = [
            match.start()
            for match in conjunction_matches
            if int(len(segment) * 0.3) <= match.start() <= int(len(segment) * 0.7)
        ]
        if preferred:
            relative = min(preferred, key=lambda pos: abs(pos - midpoint))
            return start + relative
        whitespace_matches = [match.start() for match in re.finditer(r"\s+", segment)]
        if not whitespace_matches:
            return None
        relative = min(whitespace_matches, key=lambda pos: abs(pos - midpoint))
        return start + relative

    @classmethod
    def split_long_candidate(cls, candidate: SentenceCandidate) -> list[SentenceCandidate]:
        if candidate.split_reason != "long_segment_fallback":
            return [candidate]
        if re.search(r"[.!?;:]", candidate.text):
            return [candidate]
        split_idx = cls.long_segment_break_index(candidate.text, 0, len(candidate.text))
        if split_idx is None:
            return [candidate]
        left = cls.build_sentence_candidate(
            candidate.text,
            0,
            split_idx,
            confidence=0.2,
            split_reason="long_segment_fallback",
        )
        right = cls.build_sentence_candidate(
            candidate.text,
            split_idx,
            len(candidate.text),
            confidence=0.2,
            split_reason="long_segment_fallback",
        )
        parts = [part for part in (left, right) if part is not None]
        return parts or [candidate]

    @classmethod
    def split_sentence_candidates(cls, text: str, *, block_type: str | None = None) -> list[SentenceCandidate]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        if block_type == "heading":
            return cls.split_heading_sentence_candidates(normalized)
        if block_type in {"metadata", "noise", "footer"}:
            candidate = cls.build_sentence_candidate(
                normalized, 0, len(normalized), confidence=0.25, split_reason="structure_block", block_type=block_type
            )
            return [candidate] if candidate else []
        if block_type == "list_item":
            result: list[SentenceCandidate] = []
            line_matches = list(re.finditer(r"[^\n]+", normalized))
            for match in line_matches or [re.match(r"[\s\S]+", normalized)]:
                if match is None:
                    continue
                line_start = match.start()
                line_end = match.end()
                line_text = normalized[line_start:line_end]
                line_candidates = cls.split_sentence_candidates(line_text, block_type="list_item_fragment")
                if not line_candidates:
                    candidate = cls.build_sentence_candidate(
                        normalized,
                        line_start,
                        line_end,
                        confidence=0.55,
                        split_reason="list_item_block",
                        block_type=block_type,
                    )
                    if candidate:
                        result.append(candidate)
                    continue
                for candidate in line_candidates:
                    mapped = cls.build_sentence_candidate(
                        normalized,
                        line_start + candidate.char_start_offset,
                        line_start + candidate.char_end_offset,
                        confidence=candidate.confidence,
                        split_reason="list_item_line" if candidate.split_reason == "tail" else candidate.split_reason,
                        block_type=block_type,
                    )
                    if mapped:
                        result.append(mapped)
            return result
        if block_type == "table_row":
            candidate = cls.build_sentence_candidate(
                normalized, 0, len(normalized), confidence=0.4, split_reason="table_row_block", block_type=block_type
            )
            return [candidate] if candidate else []

        candidates: list[SentenceCandidate] = []
        start = 0
        idx = 0
        text_length = len(normalized)
        paren_depth = 0

        def _append_candidate(end_idx: int, confidence: float, split_reason: str) -> None:
            nonlocal start
            split_end = end_idx
            while split_end < text_length and normalized[split_end] in "\"'”’)]}":
                split_end += 1
            candidate = cls.build_sentence_candidate(
                normalized,
                start,
                split_end,
                confidence=confidence,
                split_reason=split_reason,
                block_type=block_type,
            )
            if candidate:
                candidates.append(candidate)
            start = split_end

        while idx < text_length:
            current = normalized[idx]
            if current in "([{":
                paren_depth += 1
            elif current in ")]}":
                paren_depth = max(0, paren_depth - 1)
            elif current in ".!?" and paren_depth == 0:
                next_token = cls.next_token(normalized, idx + 1)
                capital_after = bool(next_token) and next_token[:1].isupper()
                if current == ".":
                    if (
                        cls.is_dotted_abbreviation_continuation(normalized, idx)
                        or cls.is_marker_only_fragment(normalized, start, idx)
                        or cls.is_legal_reference_boundary(normalized, idx)
                    ):
                        idx += 1
                        continue
                    if cls.is_numeric_list_boundary(normalized, idx):
                        _append_candidate(idx + 1, 0.72, "numeric_list_boundary")
                        idx = start
                        continue
                    if next_token and not capital_after:
                        idx += 1
                        continue
                if not cls.is_abbreviation_boundary(normalized, idx) and not cls.is_date_boundary(normalized, idx):
                    confidence = 0.6 + (0.2 if capital_after else 0.0)
                    _append_candidate(idx + 1, confidence, "strong_punctuation")
                    idx = start
                    continue
            elif current in ";:" and paren_depth == 0:
                next_token = cls.next_token(normalized, idx + 1)
                capital_after = bool(next_token) and next_token[:1].isupper()
                if current == ";" and capital_after:
                    _append_candidate(idx + 1, 0.7, "medium_punctuation:semicolon")
                    idx = start
                    continue
                if current == ":" and capital_after:
                    _append_candidate(idx + 1, 0.65, "medium_punctuation:colon")
                    idx = start
                    continue
            elif current == "\n":
                line_break_end = idx
                while line_break_end < text_length and normalized[line_break_end] == "\n":
                    line_break_end += 1
                next_token = cls.next_token(normalized, line_break_end)
                fragment = cls.normalize_sentence_candidate_text(normalized[start:idx])
                if fragment and next_token:
                    confidence = 0.25
                    if next_token[:1].isupper():
                        confidence += 0.15
                    if len(fragment) <= 72 or cls.sentence_word_count(fragment) <= 8:
                        confidence += 0.05
                    _append_candidate(idx, confidence, "newline_candidate")
                    idx = start
                    continue
            elif current.isspace():
                heading_match = cls._INLINE_HEADING_MARKER_PATTERN.match(normalized, idx + 1)
                marker_match = cls._LIST_MARKER_PAREN_PATTERN.match(normalized, idx + 1)
                fragment = cls.normalize_sentence_candidate_text(normalized[start:idx])
                if (
                    heading_match
                    and fragment
                    and cls.is_inline_heading_marker_start(normalized, heading_match.start(), heading_match.end())
                ):
                    _append_candidate(idx, 0.7, "hierarchical_marker")
                    idx = start
                    continue
                if marker_match and fragment and cls.is_parenthesized_list_marker_start(normalized, marker_match.start()):
                    _append_candidate(idx, 0.55, "list_marker_parenthesized")
                    idx = start
                    continue
            idx += 1

        tail = cls.build_sentence_candidate(
            normalized,
            start,
            text_length,
            confidence=0.4,
            split_reason="tail",
            block_type=block_type,
        )
        if tail:
            candidates.append(tail)

        final_candidates: list[SentenceCandidate] = []
        for candidate in candidates:
            final_candidates.extend(cls.split_long_candidate(candidate))
        return final_candidates

    @classmethod
    def split_sentences(cls, text: str, *, block_type: str | None = None) -> list[str]:
        return [candidate.text for candidate in cls.split_sentence_candidates(text, block_type=block_type)]

    @staticmethod
    def build_table_sentence_units(paragraph_text: str, paragraph_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        table_cells = [str(cell).strip() for cell in paragraph_metadata.get("table_cells") or [] if str(cell).strip()]
        if not table_cells:
            return []
        if str(paragraph_metadata.get("table_role") or "") == "header":
            return []

        headers = [str(value).strip() for value in paragraph_metadata.get("table_column_headers") or [] if str(value).strip()]
        sentence_units: list[dict[str, Any]] = []
        search_cursor = 0
        for column_index, cell_text in enumerate(table_cells, start=1):
            cell_start = paragraph_text.find(cell_text, search_cursor)
            if cell_start < 0:
                cell_start = paragraph_text.find(cell_text)
            if cell_start < 0:
                continue
            cell_end = cell_start + len(cell_text)
            search_cursor = cell_end
            header_text = headers[column_index - 1] if column_index - 1 < len(headers) else ""
            display_text = f"{header_text}: {cell_text}" if header_text and header_text.lower() != cell_text.lower() else cell_text
            sentence_units.append(
                {
                    "text": display_text,
                    "char_start_offset": cell_start,
                    "char_end_offset": cell_end,
                    "metadata": {
                        "table_column_index": column_index,
                        "table_column_header": header_text or None,
                        "table_cell_text": cell_text,
                        "table_role": paragraph_metadata.get("table_role"),
                        "is_table_cell": True,
                    },
                }
            )
        return sentence_units

    @classmethod
    def is_strong_sentence_candidate(cls, candidate: SentenceCandidate) -> bool:
        return candidate.confidence >= cls._CLAIM_STRONG_CONFIDENCE

    @classmethod
    def build_claim_refinement_budget(cls, total_blocks: int) -> int:
        return InformationValueScorer.build_claim_refinement_budget(total_blocks)

    @classmethod
    def count_claim_refinement_signals(cls, text: str) -> dict[str, int]:
        return InformationValueScorer.count_claim_refinement_signals(text)

    @classmethod
    def should_attempt_claim_refinement(
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

    @staticmethod
    def language_tag_from_metadata(metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None
        return metadata.get("language") or metadata.get("language_tag")

    @staticmethod
    def sentence_unit_from_candidate(candidate: SentenceCandidate, *, strong_split: bool) -> dict[str, Any]:
        return {
            "text": candidate.text,
            "char_start_offset": candidate.char_start_offset,
            "char_end_offset": candidate.char_end_offset,
            "metadata": {
                "split_reason": candidate.split_reason,
                "split_confidence": candidate.confidence,
                "split_strength": "strong" if strong_split else "weak",
                "uncertain_split": not strong_split,
            },
        }

    def refine_candidate_with_claim_splitter(
        self,
        paragraph_text: str,
        candidate: SentenceCandidate,
        *,
        paragraph_metadata: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        if not self._claim_fine_splitter:
            return None
        block_start = candidate.char_start_offset
        block_end = candidate.char_end_offset
        if block_start >= block_end:
            return None
        block_text = paragraph_text[block_start:block_end]
        if not block_text.strip():
            return None
        claim_candidates = self._claim_fine_splitter.split_block(
            block_text, language_tag=self.language_tag_from_metadata(paragraph_metadata)
        )
        if not claim_candidates:
            return None
        units: list[dict[str, Any]] = []
        for claim in claim_candidates:
            if claim.char_end <= claim.char_start:
                continue
            units.append(
                {
                    "text": claim.text_span,
                    "char_start_offset": block_start + claim.char_start,
                    "char_end_offset": block_start + claim.char_end,
                    "metadata": {
                        "split_reason": "claim_fine_split",
                        "claim_split_reasons": claim.split_reason,
                        "split_confidence": claim.confidence,
                        "split_strength": "claim_refined",
                        "uncertain_split": False,
                        "refined_from_reason": candidate.split_reason,
                        "refined_from_confidence": candidate.confidence,
                        "subject_hint": claim.subject_hint,
                        "predicate_hint": claim.predicate_hint,
                        "object_hint": claim.object_hint,
                    },
                }
            )
        return units or None

    def build_sentence_units_for_paragraph(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        units, _diagnostics = self.build_sentence_units_for_paragraph_with_diagnostics(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )
        return units

    def build_sentence_units_for_paragraph_with_diagnostics(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        diagnostics: dict[str, Any] = {
            "block_type": block_type,
            "fallback_used": False,
            "candidate_count": 0,
            "strong_candidate_count": 0,
            "weak_candidate_count": 0,
            "claim_refinement_attempts": 0,
            "claim_refinement_hits": 0,
            "claim_refinement_units": 0,
            "claim_refinement_gate_reason": "not_needed",
            "claim_refinement_gate_reason_counts": {},
        }
        if block_type == "table_row":
            table_units = self.build_table_sentence_units(paragraph_text, paragraph_metadata)
            if table_units:
                diagnostics["candidate_count"] = len(table_units)
                diagnostics["strong_candidate_count"] = len(table_units)
                return table_units, diagnostics
        if block_type in {"metadata", "noise", "footer"}:
            diagnostics["candidate_count"] = 1 if paragraph_text else 0
            diagnostics["strong_candidate_count"] = diagnostics["candidate_count"]
            return [{"text": paragraph_text, "metadata": {}}], diagnostics
        candidates = self.split_sentence_candidates(paragraph_text, block_type=block_type)
        if not candidates:
            fallback = self.build_sentence_candidate(
                paragraph_text,
                0,
                len(paragraph_text),
                confidence=0.4,
                split_reason="fallback_single",
                block_type=block_type,
            )
            candidates = [fallback] if fallback else []
            diagnostics["fallback_used"] = bool(fallback)
        diagnostics["candidate_count"] = len(candidates)
        units: list[dict[str, Any]] = []
        block_refinement_attempted = False
        block_refinement_hit = False
        for candidate in candidates:
            strong = self.is_strong_sentence_candidate(candidate)
            if strong:
                diagnostics["strong_candidate_count"] += 1
            else:
                diagnostics["weak_candidate_count"] += 1
            if not strong and self._enable_claim_fine_split_during_parsing:
                should_attempt, gate_reason, signal_details = self._information_value_scorer.should_attempt_claim_refinement(
                    candidate,
                    block_type=block_type,
                    refinement_state=refinement_state,
                )
                diagnostics["claim_refinement_gate_reason"] = gate_reason
                gate_reason_counts = dict(diagnostics.get("claim_refinement_gate_reason_counts") or {})
                gate_reason_counts[gate_reason] = int(gate_reason_counts.get(gate_reason) or 0) + 1
                diagnostics["claim_refinement_gate_reason_counts"] = gate_reason_counts
                diagnostics["claim_refinement_signal_score"] = signal_details.get("signal_score")
                diagnostics["claim_refinement_predicate_count"] = signal_details.get("predicate_count")
                diagnostics["claim_refinement_connector_count"] = signal_details.get("connector_count")
                diagnostics["claim_refinement_punctuation_signal_count"] = signal_details.get("punctuation_signal_count")
                if should_attempt:
                    if refinement_state is not None and not block_refinement_attempted:
                        refinement_state["attempted_blocks"] = int(refinement_state.get("attempted_blocks") or 0) + 1
                    block_refinement_attempted = True
                    diagnostics["claim_refinement_attempts"] += 1
                    refined_units = self.refine_candidate_with_claim_splitter(
                        paragraph_text,
                        candidate,
                        paragraph_metadata=paragraph_metadata,
                    )
                    if refined_units:
                        diagnostics["claim_refinement_hits"] += 1
                        diagnostics["claim_refinement_units"] += len(refined_units)
                        block_refinement_hit = True
                        units.extend(refined_units)
                        continue
            units.append(self.sentence_unit_from_candidate(candidate, strong_split=strong))
        if refinement_state is not None and block_refinement_hit:
            refinement_state["hit_blocks"] = int(refinement_state.get("hit_blocks") or 0) + 1
        return units, diagnostics


__all__ = ["SentenceUnitBuilder"]
