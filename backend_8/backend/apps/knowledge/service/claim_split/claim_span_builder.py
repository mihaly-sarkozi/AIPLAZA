from __future__ import annotations

from typing import Iterable
from collections.abc import Iterator

from .types import ComplementHints, ParsedDoc, ParsedToken, TokenSpan

HARD_BOUNDARY_TOKENS = {".", "!", "?", ";", ":"}
CLAUSE_BOUNDARY_DEPS = {"conj", "parataxis", "advcl", "ccomp"}
NOUN_PHRASE_DEPS = {"det", "amod", "compound", "flat", "fixed", "case", "nummod", "appos"}
PREDICATE_PHRASE_DEPS = {"aux", "cop", "mark", "neg", "compound:prt"}
DETACHED_PUNCTUATION_TOKENS = {","}


def _iter_anchor_tokens(
    predicate: ParsedToken,
    subject: ParsedToken | None,
    complements: ComplementHints,
) -> Iterator[ParsedToken]:
    yield predicate
    if subject:
        yield subject
    for bucket in (complements.objects, complements.attributes, complements.modifiers):
        yield from bucket


def _child_tokens(parent: ParsedToken, doc: ParsedDoc) -> list[ParsedToken]:
    return [token for token in doc.tokens if token.head_idx == parent.idx]


def _expand_anchor_phrase(anchor: ParsedToken, doc: ParsedDoc) -> set[int]:
    allowed_deps = PREDICATE_PHRASE_DEPS if anchor.pos in {"VERB", "AUX", "ADJ"} else NOUN_PHRASE_DEPS
    included = {anchor.idx}
    queue = [anchor]
    while queue:
        current = queue.pop()
        for child in _child_tokens(current, doc):
            if child.idx in included:
                continue
            if child.dep not in allowed_deps:
                continue
            included.add(child.idx)
            queue.append(child)
    return included


def _is_boundary_token(token: ParsedToken) -> bool:
    if token.pos == "PUNCT" and token.text in HARD_BOUNDARY_TOKENS:
        return True
    if token.dep in CLAUSE_BOUNDARY_DEPS:
        return True
    return False


def _is_detached_anchor(anchor: ParsedToken, predicate: ParsedToken, doc: ParsedDoc) -> bool:
    if anchor.idx == predicate.idx:
        return False
    left = min(anchor.idx, predicate.idx)
    right = max(anchor.idx, predicate.idx)
    detached_punct_count = 0
    for idx in range(left + 1, right):
        token = doc.token_by_idx(idx)
        if token is None:
            continue
        if token.dep in CLAUSE_BOUNDARY_DEPS:
            return True
        if token.pos == "PUNCT" and token.text in DETACHED_PUNCTUATION_TOKENS:
            detached_punct_count += 1
    if detached_punct_count >= 2:
        return True
    if anchor.idx < predicate.idx and detached_punct_count >= 1:
        for idx in range(anchor.idx - 1, -1, -1):
            token = doc.token_by_idx(idx)
            if token is None:
                continue
            if _is_boundary_token(token):
                break
            if token.pos == "PUNCT" and token.text in DETACHED_PUNCTUATION_TOKENS:
                return True
    if anchor.idx > predicate.idx and detached_punct_count >= 1:
        for idx in range(anchor.idx + 1, len(doc.tokens)):
            token = doc.token_by_idx(idx)
            if token is None:
                continue
            if _is_boundary_token(token):
                break
            if token.pos == "PUNCT" and token.text in DETACHED_PUNCTUATION_TOKENS:
                return True
    return False


def _nearest_left_boundary_idx(predicate: ParsedToken, doc: ParsedDoc) -> int | None:
    for idx in range(predicate.idx - 1, -1, -1):
        token = doc.token_by_idx(idx)
        if token is not None and _is_boundary_token(token):
            return idx
    return None


def _nearest_right_boundary_idx(predicate: ParsedToken, doc: ParsedDoc) -> int | None:
    for idx in range(predicate.idx + 1, len(doc.tokens)):
        token = doc.token_by_idx(idx)
        if token is not None and _is_boundary_token(token):
            return idx
    return None


def build_claim_span(
    predicate: ParsedToken,
    subject: ParsedToken | None,
    complements: ComplementHints,
    doc: ParsedDoc,
) -> TokenSpan:
    """Create a minimal span that contains predicate, optional subject and complements."""

    included_idxs: set[int] = set()
    for anchor in _iter_anchor_tokens(predicate, subject, complements):
        if _is_detached_anchor(anchor, predicate, doc):
            continue
        included_idxs.update(_expand_anchor_phrase(anchor, doc))
    if not included_idxs:
        return TokenSpan(start=predicate.idx, end=predicate.idx + 1)
    start, end = min(included_idxs), max(included_idxs)
    left_boundary_idx = _nearest_left_boundary_idx(predicate, doc)
    if left_boundary_idx is not None:
        start = max(start, left_boundary_idx + 1)
    right_boundary_idx = _nearest_right_boundary_idx(predicate, doc)
    if right_boundary_idx is not None:
        end = min(end, right_boundary_idx - 1)
    if start > end:
        return TokenSpan(start=predicate.idx, end=predicate.idx + 1)
    return TokenSpan(start=start, end=end + 1)
