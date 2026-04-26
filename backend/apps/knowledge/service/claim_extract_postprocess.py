"""ClaimExtractorV1: több claim utófeldolgozás (gyenge duplikátum, split subject)."""
from __future__ import annotations

import re

from apps.knowledge.domain.claim import Claim
from apps.knowledge.service.claim_extract_constants import (
    WEAK_DUPLICATE_MODAL_PREDICATES,
    WEAK_DUPLICATE_USE_PREDICATES,
)
from apps.knowledge.service.claim_extract_normalize import normalize_predicate, normalize_text, word_count
from apps.knowledge.service.language_rules import fold_text


def is_weak_contextual_object(object_text: str | None, *, language: str) -> bool:
    candidate = normalize_text(object_text)
    if not candidate:
        return True
    folded = fold_text(candidate)
    if language == "hu":
        return bool(re.search(r"(?:nál|nél|ban|ben|hoz|hez|höz|ként|kor)$", folded))
    if language == "en":
        return bool(re.match(r"^(?:for|at|in|on)\b", folded))
    if language == "es":
        return bool(re.match(r"^(?:para|en)\b", folded))
    return False


def drop_weak_duplicate_claims(claims: list[Claim], *, language: str) -> list[Claim]:
    if len(claims) < 2:
        return claims
    filtered: list[Claim] = []
    dropped_ids: set[str] = set()
    for claim in claims:
        if claim.claim_id in dropped_ids:
            continue
        folded_subject = fold_text(claim.subject_text)
        folded_predicate = normalize_predicate(claim.predicate_text)
        if folded_predicate not in WEAK_DUPLICATE_USE_PREDICATES.get(language, set()):
            filtered.append(claim)
            continue
        competing_modal = next(
            (
                other
                for other in claims
                if other.claim_id != claim.claim_id
                and fold_text(other.subject_text) == folded_subject
                and normalize_predicate(other.predicate_text) in WEAK_DUPLICATE_MODAL_PREDICATES.get(language, set())
                and word_count(other.object_text) >= 2
            ),
            None,
        )
        if competing_modal is not None and is_weak_contextual_object(claim.object_text, language=language):
            dropped_ids.add(claim.claim_id)
            continue
        filtered.append(claim)
    return filtered


def should_reuse_split_subject(
    subject_text: str | None,
    *,
    base_subject: str | None,
    subject_source: str | None,
) -> bool:
    if subject_source != "fallback":
        return not normalize_text(subject_text) and bool(normalize_text(base_subject))
    candidate = normalize_text(subject_text)
    base = normalize_text(base_subject)
    if not base:
        return False
    if not candidate:
        return True
    folded_candidate = fold_text(candidate)
    folded_base = fold_text(base)
    if folded_candidate == folded_base:
        return False
    if folded_candidate.startswith(folded_base + " "):
        return True
    return word_count(candidate) > max(word_count(base) + 2, 5)
