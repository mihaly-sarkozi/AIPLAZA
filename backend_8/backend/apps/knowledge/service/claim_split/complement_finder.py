from __future__ import annotations

from .types import ComplementHints, ParsedDoc, ParsedToken

OBJECT_DEPS = {"obj", "dobj", "iobj", "pobj", "obl", "nmod", "xcomp"}
ATTRIBUTE_DEPS = {"amod", "acomp", "advmod", "clfmod"}
LOCATION_DEPS = {"obl:tmod", "obl:lmod", "advmod", "nmod:loc"}
CLAUSE_BOUNDARY_DEPS = {"conj", "parataxis", "advcl", "ccomp"}
HARD_BOUNDARY_TOKENS = {".", "!", "?", ";", ":"}
LOCAL_COMPLEMENT_WINDOW = 12
LOCAL_DEPENDENCY_DEPTH = 4


def _has_hard_boundary_between(predicate: ParsedToken, token: ParsedToken, doc: ParsedDoc) -> bool:
    left = min(predicate.idx, token.idx)
    right = max(predicate.idx, token.idx)
    for idx in range(left + 1, right):
        current = doc.token_by_idx(idx)
        if current is None:
            continue
        if current.pos == "PUNCT" and current.text in HARD_BOUNDARY_TOKENS:
            return True
    return False


def _dependency_distance_to_predicate(token: ParsedToken, predicate: ParsedToken, doc: ParsedDoc) -> int | None:
    current = token
    visited: set[int] = set()
    depth = 0
    while current.head_idx is not None and depth < LOCAL_DEPENDENCY_DEPTH:
        if current.idx in visited:
            return None
        visited.add(current.idx)
        head = doc.token_by_idx(current.head_idx)
        if head is None:
            return None
        depth += 1
        if head.idx == predicate.idx:
            return depth
        current = head
        if current.dep in CLAUSE_BOUNDARY_DEPS:
            return None
    return None


def _is_clause_boundary_token(token: ParsedToken) -> bool:
    return token.dep in CLAUSE_BOUNDARY_DEPS


def _is_locally_attached_to_predicate(token: ParsedToken, predicate: ParsedToken, doc: ParsedDoc) -> bool:
    if token.idx == predicate.idx:
        return False
    if abs(token.idx - predicate.idx) > LOCAL_COMPLEMENT_WINDOW:
        return False
    if _has_hard_boundary_between(predicate, token, doc):
        return False
    if _is_clause_boundary_token(token):
        return False
    if token.head_idx == predicate.idx:
        return True
    if _dependency_distance_to_predicate(token, predicate, doc) is not None:
        return True
    return False


def find_local_complements(predicate: ParsedToken, doc: ParsedDoc) -> ComplementHints:
    hints = ComplementHints()
    for token in doc.tokens:
        if token.idx == predicate.idx:
            continue
        if not _is_locally_attached_to_predicate(token, predicate, doc):
            continue
        if token.dep in OBJECT_DEPS:
            hints.objects.append(token)
        elif token.dep in ATTRIBUTE_DEPS:
            hints.attributes.append(token)
        elif token.dep in LOCATION_DEPS:
            hints.modifiers.append(token)
        elif token.pos in {"ADP", "SCONJ", "CCONJ"}:
            hints.extras.append(token)
        elif token.pos in {"NOUN", "PROPN"} and token.dep.startswith("nmod"):
            hints.objects.append(token)
    return hints
