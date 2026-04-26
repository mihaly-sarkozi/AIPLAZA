from __future__ import annotations

from .types import ClaimCandidate, ParsedDoc

HARD_BOUNDARY_TOKENS = {".", "!", "?", ";"}
MERGE_CONNECTOR_TOKENS = {",", "és", "vagy", "illetve", "valamint", "is"}


def _gap_tokens(first: ClaimCandidate, second: ClaimCandidate, doc: ParsedDoc) -> list[str]:
    return [token.text.lower() for token in doc.tokens[first.end_token : second.start_token]]


def _has_hard_boundary(tokens: list[str]) -> bool:
    return any(token in HARD_BOUNDARY_TOKENS for token in tokens)


def _has_candidate_edge_boundary(first: ClaimCandidate, second: ClaimCandidate, doc: ParsedDoc) -> bool:
    left_edge = doc.token_by_idx(first.end_token - 1)
    right_prev = doc.token_by_idx(second.start_token - 1) if second.start_token > 0 else None
    return any(
        token is not None and token.text.lower() in HARD_BOUNDARY_TOKENS
        for token in (left_edge, right_prev)
    )


def _is_mergeable_connector_sequence(tokens: list[str]) -> bool:
    if not tokens:
        return True
    return all(token in MERGE_CONNECTOR_TOKENS for token in tokens)


def _should_merge(first: ClaimCandidate, second: ClaimCandidate, doc: ParsedDoc) -> bool:
    if not first.subject_hint or not second.subject_hint:
        return False
    if first.subject_hint != second.subject_hint:
        return False
    distance = second.start_token - first.end_token
    if distance > 3:
        return False
    if _has_candidate_edge_boundary(first, second, doc):
        return False
    gap_tokens = _gap_tokens(first, second, doc)
    if _has_hard_boundary(gap_tokens):
        return False
    if not _is_mergeable_connector_sequence(gap_tokens):
        return False
    return True


def _merge_candidates(
    first: ClaimCandidate,
    second: ClaimCandidate,
    doc: ParsedDoc,
) -> ClaimCandidate:
    start = min(first.start_token, second.start_token)
    end = max(first.end_token, second.end_token)
    merged_text = doc.span_text(start, end)
    start_char = doc.tokens[start].char_start if doc.tokens else 0
    end_char = doc.tokens[end - 1].char_end if doc.tokens and end > start else start_char
    return ClaimCandidate(
        text_span=merged_text,
        subject_hint=first.subject_hint,
        predicate_hint=f"{first.predicate_hint}|{second.predicate_hint}",
        object_hint=second.object_hint or first.object_hint,
        start_token=start,
        end_token=end,
        char_start=start_char,
        char_end=end_char,
        confidence=max(first.confidence, second.confidence),
        split_reason=first.split_reason + second.split_reason + ["consolidated"],
    )


def merge_or_split_adjacent_candidates(
    candidates: list[ClaimCandidate],
    doc: ParsedDoc,
) -> list[ClaimCandidate]:
    merged: list[ClaimCandidate] = []
    for candidate in candidates:
        if merged and _should_merge(merged[-1], candidate, doc):
            merged[-1] = _merge_candidates(merged[-1], candidate, doc)
            continue
        merged.append(candidate)
    return merged
