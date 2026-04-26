"""ClaimExtractorV1: predikátumok keresése és összevonása a mondatban."""
from __future__ import annotations

import re

from apps.knowledge.service.claim_extract_constants import (
    PredicateMatch,
    STATE_AUXILIARIES,
    STATE_COMPLEMENTS,
)
from apps.knowledge.service.claim_extract_normalize import normalize_predicate
from apps.knowledge.service.language_rules import fold_text, get_language_rules


def folded_with_index_map(text: str) -> tuple[str, list[int]]:
    folded_chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        folded = fold_text(char)
        if not folded:
            continue
        for folded_char in folded:
            folded_chars.append(folded_char)
            index_map.append(index)
    return "".join(folded_chars), index_map


def find_predicates(text: str, *, language: str) -> list[PredicateMatch]:
    folded_text, index_map = folded_with_index_map(text)
    if not folded_text:
        return []
    occupied: list[tuple[int, int]] = []
    matches: list[PredicateMatch] = []
    for keyword in sorted(get_language_rules(language).predicate_keywords, key=len, reverse=True):
        folded_keyword = fold_text(keyword)
        pattern = re.compile(r"\b" + re.escape(folded_keyword) + r"\b")
        for match in pattern.finditer(folded_text):
            start, end = match.span()
            if any(not (end <= occ_start or start >= occ_end) for occ_start, occ_end in occupied):
                continue
            original_start = index_map[start]
            original_end = index_map[end - 1] + 1
            matches.append(PredicateMatch((text[original_start:original_end], original_start, original_end)))
            occupied.append((start, end))
    return sorted(matches, key=lambda item: item.start)


def merge_compound_predicates(matches: list[PredicateMatch], text: str, *, language: str) -> list[PredicateMatch]:
    if not matches:
        return matches
    merged: list[PredicateMatch] = []
    idx = 0
    filler_words = get_language_rules(language).filler_words
    while idx < len(matches):
        current = matches[idx]
        if idx + 1 < len(matches):
            following = matches[idx + 1]
            current_norm = normalize_predicate(current.predicate)
            next_norm = normalize_predicate(following.predicate)
            gap_text = text[current.end : following.start]
            folded_gap = fold_text(gap_text)
            for filler in filler_words:
                folded_gap = re.sub(r"\b" + re.escape(fold_text(filler)) + r"\b", "", folded_gap)
            folded_gap = re.sub(r"\s+", " ", folded_gap).strip()
            if current_norm in STATE_AUXILIARIES.get(language, set()) and next_norm in STATE_COMPLEMENTS.get(language, set()) and not folded_gap:
                merged.append(PredicateMatch((text[current.start : following.end], current.start, following.end)))
                idx += 2
                continue
        merged.append(current)
        idx += 1
    return merged


def should_skip_predicate(current: PredicateMatch, previous: PredicateMatch | None, *, text: str, language: str) -> bool:
    from apps.knowledge.service.claim_extract_constants import MODAL_PREDICATES

    if previous is None:
        return False
    previous_norm = normalize_predicate(previous.predicate)
    if previous_norm not in MODAL_PREDICATES.get(language, set()):
        return False
    between = text[previous.end : current.start]
    if any(char in between for char in ",;:."):
        return False
    conjunctions = get_language_rules(language).conjunction_keywords
    folded_between = fold_text(between)
    if any(re.search(r"\b" + re.escape(fold_text(item)) + r"\b", folded_between) for item in conjunctions):
        return False
    return True
