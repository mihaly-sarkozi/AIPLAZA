"""ClaimExtractorV1: szöveg- és predikátum-normalizálás."""
from __future__ import annotations

from apps.knowledge.service.claim_extract_constants import TRIM_CHARS
from apps.knowledge.service.language_rules import fold_text


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def word_count(value: str | None) -> int:
    return len([token for token in normalize_text(value).split() if token])


def sentence_text(sentence: object) -> str:
    return getattr(sentence, "text", getattr(sentence, "text_content", None) or "")


def normalize_predicate(value: str | None) -> str:
    return fold_text(normalize_text(value))
