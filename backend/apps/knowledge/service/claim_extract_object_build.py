"""ClaimExtractorV1: predikátum előtti/utáni tárgy összeállítása."""
from __future__ import annotations

import re

from apps.knowledge.domain.mention import Mention
from apps.knowledge.service.claim_extract_constants import MODAL_PREDICATES, TRIM_CHARS, USE_PREDICATE_FOLDS
from apps.knowledge.service.claim_extract_hu_use import hu_is_hasznal_purpose_tail_remainder
from apps.knowledge.service.claim_extract_mentions import select_object_mention
from apps.knowledge.service.claim_extract_normalize import normalize_predicate, normalize_text, word_count
from apps.knowledge.service.claim_extract_text_clean import (
    build_relation_title_object,
    clean_object_slice,
    find_local_clause_start,
    is_temporal_tail_token,
    should_prefer_relation_title_object,
    strip_leading_stopwords,
    strip_trailing_conjunctions,
    strip_trailing_fillers,
    trim_clause_break,
)
from apps.knowledge.service.language_rules import fold_text


def build_pre_predicate_object_text(
    text: str,
    *,
    subject_mention: Mention | None,
    predicate_idx: int | None,
    language: str,
    subject_text: str | None = None,
    clause_start_idx: int = 0,
) -> str | None:
    if predicate_idx is None:
        return None
    candidate = ""
    if subject_mention is not None:
        start_idx = max(subject_mention.char_end, clause_start_idx)
        candidate = text[start_idx:predicate_idx].strip(TRIM_CHARS)
    elif subject_text:
        pre_predicate_text = strip_trailing_conjunctions(
            strip_trailing_fillers(
                strip_leading_stopwords(text[clause_start_idx:predicate_idx].strip(TRIM_CHARS), language=language),
                language=language,
            ),
            language=language,
        )
        pre_tokens = normalize_text(pre_predicate_text).split()
        subject_tokens = normalize_text(subject_text).split()
        if pre_tokens[: len(subject_tokens)] == subject_tokens:
            candidate = " ".join(pre_tokens[len(subject_tokens) :]).strip(TRIM_CHARS)
    candidate = clean_object_slice(candidate, language=language)
    candidate = trim_clause_break(candidate, language=language)
    if not candidate:
        return None
    if subject_text and fold_text(candidate) == fold_text(subject_text):
        return None
    return candidate


def build_object_text(
    text: str,
    *,
    mentions: list[Mention],
    predicate: str,
    predicate_end_idx: int | None,
    predicate_idx: int | None,
    language: str,
    next_predicate_idx: int | None = None,
    subject_text: str | None = None,
    subject_mention: Mention | None = None,
    hu_hasznal_subject_end: int | None = None,
) -> str | None:
    remainder = (
        text[predicate_end_idx : next_predicate_idx if next_predicate_idx is not None else None].strip(TRIM_CHARS)
        if predicate_end_idx is not None
        else None
    )
    clause_start_idx = find_local_clause_start(text, predicate_idx)
    pre_predicate_object: str | None
    if (
        hu_hasznal_subject_end is not None
        and predicate_idx is not None
        and language == "hu"
        and normalize_predicate(predicate) in USE_PREDICATE_FOLDS.get(language, set())
    ):
        gap_raw = text[hu_hasznal_subject_end:predicate_idx].strip(TRIM_CHARS)
        pre_predicate_object = clean_object_slice(gap_raw, language=language) if gap_raw else None
        if pre_predicate_object:
            pre_predicate_object = trim_clause_break(pre_predicate_object, language=language) or None
        if not pre_predicate_object:
            pre_predicate_object = None
    else:
        pre_predicate_object = build_pre_predicate_object_text(
            text,
            subject_mention=subject_mention,
            predicate_idx=predicate_idx,
            language=language,
            subject_text=subject_text,
            clause_start_idx=clause_start_idx,
        )
    if (
        language == "en"
        and pre_predicate_object
        and normalize_predicate(predicate) in USE_PREDICATE_FOLDS.get(language, set())
        and re.fullmatch(r"(?:does|do|did)\s+not", pre_predicate_object, flags=re.IGNORECASE)
    ):
        pre_predicate_object = None
    if predicate_end_idx is None:
        return None
    if remainder:
        if language == "en" and normalize_predicate(predicate) in USE_PREDICATE_FOLDS.get(language, set()):
            remainder = re.sub(
                r"^(?:(?:does|do|did)\s+not\s+|not\s+)",
                "",
                remainder,
                flags=re.IGNORECASE,
            ).strip(TRIM_CHARS)
        remainder = clean_object_slice(remainder, language=language)
        remainder = trim_clause_break(remainder, language=language)
        if subject_text and fold_text(remainder) == fold_text(subject_text):
            remainder = None
    if pre_predicate_object and should_prefer_relation_title_object(predicate, remainder, language=language):
        return build_relation_title_object(pre_predicate_object, predicate)
    if pre_predicate_object and remainder and normalize_predicate(predicate) in USE_PREDICATE_FOLDS.get(language, set()):
        if language == "hu" and hu_is_hasznal_purpose_tail_remainder(remainder):
            return clean_object_slice(pre_predicate_object, language=language) or pre_predicate_object
        return clean_object_slice(f"{pre_predicate_object} {remainder}", language=language) or pre_predicate_object
    if pre_predicate_object and remainder:
        if word_count(pre_predicate_object) >= 1 and any(
            is_temporal_tail_token(token, language=language) for token in normalize_text(pre_predicate_object).split()
        ) and not any(
            is_temporal_tail_token(token, language=language) for token in normalize_text(remainder).split()
        ):
            return pre_predicate_object
        if (
            language == "hu"
            and normalize_predicate(predicate) not in MODAL_PREDICATES.get(language, set())
            and word_count(remainder) <= 2
            and word_count(pre_predicate_object) >= 2
        ):
            return pre_predicate_object
    if remainder:
        return remainder
    object_mention = select_object_mention(
        mentions,
        predicate_end_idx=predicate_end_idx,
        next_predicate_idx=next_predicate_idx,
        language=language,
    )
    if object_mention is not None:
        return clean_object_slice(object_mention.surface_text, language=language) or None
    return pre_predicate_object


def fallback_subject(text: str, predicate_idx: int | None, *, language: str) -> str:
    from apps.knowledge.service.claim_extract_text_clean import clean_subject_slice

    if predicate_idx is None:
        words = text.split()
        return clean_subject_slice(" ".join(words[:2]).strip(TRIM_CHARS) if words else "", language=language)
    if predicate_idx <= 0:
        words = text.split()
        return clean_subject_slice(" ".join(words[:2]).strip(TRIM_CHARS) if words else "", language=language)
    subject_part = clean_subject_slice(text[:predicate_idx].strip(TRIM_CHARS), language=language)
    if not subject_part:
        return ""
    return subject_part.strip(TRIM_CHARS)
