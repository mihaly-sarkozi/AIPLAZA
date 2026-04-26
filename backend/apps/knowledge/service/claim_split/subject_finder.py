from __future__ import annotations

from typing import Iterable

from .types import ParsedDoc, ParsedToken

SUBJECT_DEPS = {"nsubj", "nsubj:pass", "csubj", "nsubj:refl", "nsubj:ext"}
FALLBACK_SUBJECT_POS = {"NOUN", "PRON", "PROPN"}
FALLBACK_FORBIDDEN_DEPS = {"obj", "iobj", "obl", "vocative", "dislocated", "expl", "punct", "case", "det", "cc", "mark"}
HARD_BOUNDARY_TOKENS = {".", "!", "?", ";", ":"}
SUBJECT_FALLBACK_WINDOW = 12
SUBJECT_FALLBACK_MAX_HEAD_DEPTH = 2
PRO_DROP_LANGUAGES = {"es"}


def _matches_subject_dep(token: ParsedToken) -> bool:
    return token.dep in SUBJECT_DEPS


def _is_hard_boundary(token: ParsedToken) -> bool:
    return token.pos == "PUNCT" and token.text in HARD_BOUNDARY_TOKENS


def _is_fallback_subject_candidate(token: ParsedToken) -> bool:
    if token.pos not in FALLBACK_SUBJECT_POS:
        return False
    if token.dep in FALLBACK_FORBIDDEN_DEPS:
        return False
    return True


def _dependency_distance_to_predicate(token: ParsedToken, predicate: ParsedToken, doc: ParsedDoc) -> int | None:
    distance = 0
    current = token
    visited: set[int] = set()
    while current.head_idx is not None and distance < SUBJECT_FALLBACK_MAX_HEAD_DEPTH:
        if current.head_idx == predicate.idx:
            return distance + 1
        if current.head_idx in visited:
            return None
        visited.add(current.head_idx)
        parent = doc.token_by_idx(current.head_idx)
        if parent is None:
            return None
        current = parent
        distance += 1
    return None


def _is_locally_attached_subject_candidate(token: ParsedToken, predicate: ParsedToken, doc: ParsedDoc) -> bool:
    return _dependency_distance_to_predicate(token, predicate, doc) is not None


def _normalized_language_tag(doc: ParsedDoc) -> str:
    return (doc.language_tag or "").split("-")[0].lower()


def _is_pro_drop_language(doc: ParsedDoc) -> bool:
    return _normalized_language_tag(doc) in PRO_DROP_LANGUAGES


def _has_forbidden_subject_marker_child(token: ParsedToken, doc: ParsedDoc) -> bool:
    for candidate in doc.tokens:
        if candidate.head_idx != token.idx:
            continue
        if candidate.dep in {"case", "mark"}:
            return True
    return False


def _is_spanish_safe_fallback_candidate(token: ParsedToken, doc: ParsedDoc) -> bool:
    if token.pos in {"PRON", "PROPN"}:
        return True
    return not _has_forbidden_subject_marker_child(token, doc)


def find_best_subject(predicate: ParsedToken, doc: ParsedDoc) -> ParsedToken | None:
    """Heuristic search for a subject candidate around the predicate."""

    explicit_subjects = [token for token in doc.tokens if token.head_idx == predicate.idx and _matches_subject_dep(token)]
    if explicit_subjects:
        for token in explicit_subjects:
            if token.idx < predicate.idx:
                return token
    is_pro_drop_language = _is_pro_drop_language(doc)

    def iterate_candidates() -> Iterable[ParsedToken]:
        lower_bound = max(0, predicate.idx - SUBJECT_FALLBACK_WINDOW)
        if not is_pro_drop_language:
            for token in doc.tokens:
                if token.idx < lower_bound or token.idx >= predicate.idx:
                    continue
                if token.head_idx == predicate.idx and _is_fallback_subject_candidate(token):
                    yield token
        elif predicate.pos in {"ADJ", "AUX"}:
            for idx in range(predicate.idx - 1, lower_bound - 1, -1):
                token = doc.tokens[idx]
                if _is_hard_boundary(token):
                    break
                if (
                    _is_fallback_subject_candidate(token)
                    and _is_locally_attached_subject_candidate(token, predicate, doc)
                    and _is_spanish_safe_fallback_candidate(token, doc)
                ):
                    yield token
            return
        else:
            return
        for idx in range(predicate.idx - 1, lower_bound - 1, -1):
            token = doc.tokens[idx]
            if _is_hard_boundary(token):
                break
            if _is_fallback_subject_candidate(token) and _is_locally_attached_subject_candidate(token, predicate, doc):
                yield token

    for token in iterate_candidates():
        if token.idx < predicate.idx:
            return token
    return None
