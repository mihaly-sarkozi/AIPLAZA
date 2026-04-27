"""ClaimExtractorV1: mention kiválasztás subject/object illesztéshez."""
from __future__ import annotations

from apps.knowledge.domain.mention import Mention
from apps.knowledge.service.claim_extract_constants import (
    MENTION_TYPE_PRIORITY,
    USE_SUBJECT_MENTION_TYPES,
)
from apps.knowledge.service.claim_extract_normalize import normalize_text
from apps.knowledge.service.claim_extract_text_clean import is_stopword_text, is_valid_subject_text, is_year_only
from apps.knowledge.service.language_rules import fold_text


def find_best_mention_id(mentions: list[Mention], text_value: str | None) -> str | None:
    folded_value = fold_text(normalize_text(text_value))
    if not folded_value:
        return None
    for mention in mentions:
        mention_value = fold_text(normalize_text(mention.surface_text or mention.normalized_text))
        if mention_value == folded_value:
            return mention.mention_id
    for mention in mentions:
        mention_value = fold_text(normalize_text(mention.surface_text or mention.normalized_text))
        if mention_value and (mention_value in folded_value or folded_value in mention_value):
            return mention.mention_id
    return None


def mention_priority(mention: Mention) -> tuple[int, int, int]:
    return (
        MENTION_TYPE_PRIORITY.get(str(mention.mention_type or "unknown"), 99),
        mention.char_start,
        -(mention.char_end - mention.char_start),
    )


_LOCATION_QUALIFIERS = {"office", "branch", "center", "centre", "iroda", "fiók", "fiok", "központ", "kozpont", "oficina", "sucursal", "centro"}


def _is_location_qualifier_compound(mention: Mention) -> bool:
    if str(mention.mention_type or "") != "location":
        return False
    tokens = {fold_text(part) for part in str(mention.surface_text or "").split() if part}
    return bool(tokens & _LOCATION_QUALIFIERS and len(tokens) >= 2)


def use_mention_type_rank(mention: Mention) -> int:
    key = str(mention.mention_type or "unknown")
    if key == "module":
        return 0
    if key == "feature":
        return 1
    if key in {"software", "product"}:
        return 2
    return 99


def select_use_subject_mention(mentions: list[Mention], *, predicate_idx: int | None, language: str) -> Mention | None:
    if predicate_idx is None:
        return None
    candidates = [
        mention
        for mention in mentions
        if str(mention.mention_type or "") in USE_SUBJECT_MENTION_TYPES
        and mention.char_end <= predicate_idx
        and is_valid_subject_text(mention.surface_text, language=language)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (use_mention_type_rank(item), item.char_start))[0]


def select_subject_mention(mentions: list[Mention], *, predicate_idx: int | None, language: str) -> Mention | None:
    if predicate_idx is None:
        return None
    candidates = [
        mention
        for mention in mentions
        if mention.char_end <= predicate_idx and is_valid_subject_text(mention.surface_text, language=language)
    ]
    if not candidates:
        return None
    compound_locations = [mention for mention in candidates if _is_location_qualifier_compound(mention)]
    if compound_locations:
        return sorted(compound_locations, key=lambda item: (item.char_start, -(item.char_end - item.char_start)))[0]
    return sorted(candidates, key=mention_priority)[0]


def select_object_mention(
    mentions: list[Mention],
    *,
    predicate_end_idx: int | None,
    next_predicate_idx: int | None,
    language: str,
) -> Mention | None:
    if predicate_end_idx is None:
        return None
    candidates = [
        mention
        for mention in mentions
        if mention.char_start >= predicate_end_idx
        and (next_predicate_idx is None or mention.char_end <= next_predicate_idx)
        and not is_stopword_text(mention.surface_text, language=language)
        and not is_year_only(mention.surface_text)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.char_start, mention_priority(item)))[0]
