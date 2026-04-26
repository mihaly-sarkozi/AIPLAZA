"""ClaimExtractorV1: magyar „használ” / use-head heurisztikák."""
from __future__ import annotations

import re

from apps.knowledge.domain.mention import Mention
from apps.knowledge.service.claim_extract_constants import TRIM_CHARS, USE_SUBJECT_MENTION_TYPES
from apps.knowledge.service.claim_extract_normalize import normalize_text
from apps.knowledge.service.claim_patterns_hu import HU_USE_PREDICATE_FOLDS, USE_HEAD_PHRASE_RE


def hu_find_best_use_head_span(head: str) -> tuple[str, int] | None:
    """HU: predicate előtti utolsó modul/rendszer/szoftver/feature/product/system NP és végpozíció a ``head``-ben."""
    candidate = head.strip(TRIM_CHARS)
    if not candidate:
        return None
    best: tuple[int, str] | None = None
    for m in USE_HEAD_PHRASE_RE.finditer(candidate):
        raw = m.group(0).strip(TRIM_CHARS)
        if not raw:
            continue
        end = m.end()
        if best is None or end > best[0]:
            best = (end, raw)
    if best is None:
        return None
    phrase, end_idx = best[1], best[0]
    return phrase, end_idx


def hu_hasznal_use_subject_end_char(
    *,
    language: str,
    pred_f: str,
    predicate_idx: int | None,
    subject_mention: Mention | None,
    subject_source: str,
    use_head_end_idx: int | None,
) -> int | None:
    if language != "hu" or predicate_idx is None:
        return None
    if pred_f not in HU_USE_PREDICATE_FOLDS:
        return None
    if subject_mention is not None and str(subject_mention.mention_type or "") in USE_SUBJECT_MENTION_TYPES:
        return subject_mention.char_end
    if subject_source == "hu_use_head_heuristic" and use_head_end_idx is not None:
        return use_head_end_idx
    return None


def hu_is_hasznal_purpose_tail_remainder(remainder: str) -> bool:
    r = normalize_text(remainder).strip(TRIM_CHARS).rstrip(".")
    if len(r) < 4:
        return False
    return bool(
        re.search(r"(?:ás|és)ához\b|(?:ás|és)éhez\b", r, flags=re.IGNORECASE)
        or re.search(r"\b(?:hoz|hez|höz)\s*$", r, flags=re.IGNORECASE)
    )
