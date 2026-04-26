"""Közös claim-szintű tisztítás (subject/object): cikkek, kötőszó-szivárgás, idő tokenek.

Nem tartalmaz nyelvspecifikus **extrakciós** mintákat, csak normalizálást és csonkítást.
"""
from __future__ import annotations

import re

from apps.knowledge.service.claim_extract_constants import (
    OBJECT_LEADING_FILLERS,
    SUBJECT_TIME_PATTERNS,
    TEMPORAL_TAIL_KEYWORDS,
    TRIM_CHARS,
    UNCERTAINTY_MARKERS,
    YEAR_PATTERN,
)
from apps.knowledge.service.claim_extract_normalize import normalize_text
from apps.knowledge.service.language_rules import fold_text, get_language_rules

# Cikkek (explicit lista; nem extraction, csak trim)
SANITIZER_ARTICLES: dict[str, tuple[str, ...]] = {
    "hu": ("a", "az", "egy"),
    "en": ("the", "a", "an"),
    "es": ("el", "la", "los", "las", "un", "una"),
}

BAD_SUBJECT_PRONOUNS: dict[str, frozenset[str]] = {
    "hu": frozenset({fold_text("ez"), fold_text("ő"), fold_text("ők")}),
    "en": frozenset({fold_text("it"), fold_text("she"), fold_text("he"), fold_text("they"), fold_text("we")}),
    "es": frozenset({fold_text("ella"), fold_text("él"), fold_text("esto"), fold_text("esta")}),
}

BAD_SUBJECT_STANDALONE_ROLE_WORDS = frozenset({"responsible", "responsable"})

_ES_CONJUGATED_VERB_SUBJECT_RE = re.compile(
    r"^(?:estaba|estaban|fue|era)\s+\w+",
    flags=re.IGNORECASE | re.UNICODE,
)
_ES_PARTICIPLE_ONLY_SUBJECT_RE = re.compile(
    r"^\w+(?:ado|ada|idos|idas|ido|ida)$",
    flags=re.IGNORECASE | re.UNICODE,
)
_TRAILING_NEGATION_TOKEN_RE: dict[str, re.Pattern[str]] = {
    "hu": re.compile(r"\bnem\s*$", flags=re.IGNORECASE | re.UNICODE),
    "en": re.compile(r"\bnot\s*$", flags=re.IGNORECASE | re.UNICODE),
    "es": re.compile(r"\bno\s*$", flags=re.IGNORECASE | re.UNICODE),
}

# Kötőszó „szivárgás” a chunk végén (vagy elején)
SANITIZER_CONJUNCTION_LEAK: dict[str, tuple[str, ...]] = {
    "hu": ("de", "viszont"),
    "en": ("but", "however"),
    "es": ("pero",),
}

# Spec: weak auxiliary copula a subject elején — pl. "Fue actualizada", "Was created".
# A sanitizer leveszi az auxiliary-t és "weak_auxiliary_subject_strip" tag-et tesz,
# amelyet a quality gate `weak_auxiliary_claim_rejected_count` counterbe szed.
SUBJECT_WEAK_AUXILIARY_PREFIXES: dict[str, tuple[str, ...]] = {
    "hu": ("volt", "lett", "lesz"),
    "en": ("was", "is", "are", "were", "be"),
    "es": ("fue", "es", "era", "esta", "está"),
}


# Spec: Temporal opener prefixek subject elején — ezek nem részei az entity névnek.
# Pl. "Later, the account was updated…" → subject = "the account" (nem "Later, the account").
# A sanitizer "temporal_opener_strip" tag-gel jelöli a változást.
SUBJECT_TEMPORAL_OPENER_PREFIXES: dict[str, tuple[str, ...]] = {
    "hu": (
        "korábban",
        "korabban",
        "később",
        "kesobb",
        "azelőtt",
        "azelott",
        "régen",
        "regen",
        "valamikor",
    ),
    "en": (
        "later",
        "previously",
        "earlier",
        "before",
        "afterwards",
        "subsequently",
    ),
    "es": (
        "anteriormente",
        "antes",
        "después",
        "despues",
        "luego",
        "más tarde",
        "mas tarde",
    ),
}

# Forrásjelző prefixek, amelyek nem részei az entity subjectnek.
SUBJECT_SOURCE_PHRASE_PREFIXES: dict[str, tuple[str, ...]] = {
    "hu": (
        "a dokumentum szerint",
        "dokumentum szerint",
        "a forrás szerint",
        "a forras szerint",
        "forrás szerint",
        "forras szerint",
        "a szöveg szerint",
        "a szoveg szerint",
        "a riport szerint",
    ),
    "en": (
        "according to the document",
        "according to the source",
        "document says",
        "the document says",
        "report states that",
        "the report states that",
        "report states",
        "the report states",
    ),
    "es": (
        "según el documento",
        "segun el documento",
        "según la fuente",
        "segun la fuente",
        "el documento indica",
    ),
}


def normalize_claim_text(text: str | None) -> str:
    """Egységes whitespace + szélső TRIM_CHARS."""
    if text is None:
        return ""
    return normalize_text(text).strip(TRIM_CHARS)


def trim_articles(text: str | None, *, language: str) -> str:
    """Vezető cikkek eltávolítása (többször is, pl. „a az X”)."""
    candidate = normalize_claim_text(text)
    articles = SANITIZER_ARTICLES.get(language) or SANITIZER_ARTICLES["en"]
    if not articles or not candidate:
        return candidate
    pattern = re.compile(
        r"^(?:" + "|".join(re.escape(a) for a in sorted(articles, key=len, reverse=True)) + r")\b\s*",
        flags=re.IGNORECASE,
    )
    while candidate:
        updated = pattern.sub("", candidate, count=1).strip(TRIM_CHARS)
        if updated == candidate:
            break
        candidate = updated
    return candidate


def trim_conjunction_leak(text: str | None, *, language: str) -> str:
    """Kötőszó maradék levágása elején és végén (szűk lista)."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    leaks = SANITIZER_CONJUNCTION_LEAK.get(language, ())
    if not leaks:
        return candidate
    esc = "|".join(re.escape(x) for x in sorted(leaks, key=len, reverse=True))
    leading = re.compile(r"^(?:" + esc + r")\b[\s,;:-]*", flags=re.IGNORECASE)
    trailing = re.compile(r"[\s,;:-]*\b(?:" + esc + r")\b\s*$", flags=re.IGNORECASE)
    prev = None
    while prev != candidate:
        prev = candidate
        candidate = leading.sub("", candidate).strip(TRIM_CHARS)
        candidate = trailing.sub("", candidate).strip(TRIM_CHARS)
    return candidate


def strip_leading_source_phrase(text: str | None, *, language: str) -> str:
    """Forrásjelző mondatkezdet levágása subjectből, pl. „A dokumentum szerint Nagy Eszter”."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    prefixes = SUBJECT_SOURCE_PHRASE_PREFIXES.get(language, ())
    if not prefixes:
        return candidate
    pattern = re.compile(
        r"^(?:"
        + "|".join(re.escape(item) for item in sorted(prefixes, key=len, reverse=True))
        + r")\b[\s,;:–-]*",
        flags=re.IGNORECASE,
    )
    updated = pattern.sub("", candidate, count=1).strip(TRIM_CHARS)
    return updated


def strip_leading_temporal_opener(text: str | None, *, language: str) -> str:
    """Spec: vezető temporal opener (Later, Korábban, Anteriormente, …) levágása subjectből."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    prefixes = SUBJECT_TEMPORAL_OPENER_PREFIXES.get(language, ())
    if not prefixes:
        return candidate
    pattern = re.compile(
        r"^(?:"
        + "|".join(re.escape(item) for item in sorted(prefixes, key=len, reverse=True))
        + r")\b[\s,;:–-]*",
        flags=re.IGNORECASE,
    )
    updated = pattern.sub("", candidate, count=1).strip(TRIM_CHARS)
    return updated


def strip_leading_weak_auxiliary(text: str | None, *, language: str) -> str:
    """Spec: vezető weak auxiliary (Fue, Was, Is, Volt, …) levágása subjectből, ha követi azt egy V-ado/-ed/-t."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    prefixes = SUBJECT_WEAK_AUXILIARY_PREFIXES.get(language, ())
    if not prefixes:
        return candidate
    pattern = re.compile(
        r"^(?:"
        + "|".join(re.escape(item) for item in sorted(prefixes, key=len, reverse=True))
        + r")\s+(?=[A-Za-záéíóöőúüűñ]+(?:ado|ada|ido|ida|ed|ió|t)\b)",
        flags=re.IGNORECASE,
    )
    updated = pattern.sub("", candidate, count=1).strip(TRIM_CHARS)
    return updated


def has_leading_weak_auxiliary(text: str | None, *, language: str) -> bool:
    candidate = normalize_claim_text(text)
    if not candidate:
        return False
    prefixes = SUBJECT_WEAK_AUXILIARY_PREFIXES.get(language, ())
    pattern = re.compile(
        r"^(?:"
        + "|".join(re.escape(item) for item in sorted(prefixes, key=len, reverse=True))
        + r")\s+(?=[A-Za-záéíóöőúüűñ]+(?:ado|ada|ido|ida|ed|ió|t)\b)",
        flags=re.IGNORECASE,
    )
    return bool(pattern.match(candidate))


def has_leading_temporal_opener(text: str | None, *, language: str) -> bool:
    candidate = normalize_claim_text(text)
    if not candidate:
        return False
    prefixes = SUBJECT_TEMPORAL_OPENER_PREFIXES.get(language, ())
    return any(
        re.match(r"^" + re.escape(prefix) + r"\b", candidate, flags=re.IGNORECASE)
        for prefix in sorted(prefixes, key=len, reverse=True)
    )


def has_leading_source_phrase(text: str | None, *, language: str) -> bool:
    candidate = normalize_claim_text(text)
    if not candidate:
        return False
    prefixes = SUBJECT_SOURCE_PHRASE_PREFIXES.get(language, ())
    return any(
        re.match(r"^" + re.escape(prefix) + r"\b", candidate, flags=re.IGNORECASE)
        for prefix in sorted(prefixes, key=len, reverse=True)
    )


def _normalize_hu_subject_token_case_suffix(token: str) -> str:
    if len(token) <= 3:
        return token
    lowered = token.lower()
    for suffix in ("nál", "nél", "nak", "nek", "ban", "ben"):
        if lowered.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    # Az -n rag túl általános; csak hosszú/ékezetes magánhangzó után vágjuk (pl. felhasználón).
    if lowered.endswith("n") and len(token) > 4 and token[-2:].lower()[0] in "áéíóöőúüű":
        return token[:-1]
    return token


def normalize_hu_subject_case_suffix(text: str | None) -> str:
    """Egyszerű HU subject rag-normalizálás v1: nak/nek, n, ban/ben, nál/nél."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    tokens = candidate.split()
    return normalize_claim_text(" ".join(_normalize_hu_subject_token_case_suffix(token) for token in tokens))


def subject_sanitizer_tags(raw: str | None, cleaned: str | None, *, language: str) -> list[str]:
    """Trace-friendly sanitizer jelölők a subject raw/cleaned összevetésére."""
    tags: list[str] = []
    raw_text = normalize_claim_text(raw)
    cleaned_text = normalize_claim_text(cleaned)
    if not raw_text or raw_text == cleaned_text:
        return tags
    source_stripped = strip_leading_source_phrase(raw_text, language=language)
    if has_leading_source_phrase(raw_text, language=language) and source_stripped != raw_text:
        tags.append("source_phrase")
    # Spec: weak auxiliary copula detektálás (Fue, Was, Is, Volt, …).
    weak_aux_stripped = strip_leading_weak_auxiliary(source_stripped, language=language)
    if (
        has_leading_weak_auxiliary(source_stripped, language=language)
        and weak_aux_stripped != source_stripped
    ):
        tags.append("weak_auxiliary_subject_strip")
    # Spec: temporal opener prefix detektálás (Later, Korábban, Anteriormente, …).
    temporal_stripped = strip_leading_temporal_opener(weak_aux_stripped, language=language)
    if (
        has_leading_temporal_opener(weak_aux_stripped, language=language)
        and temporal_stripped != weak_aux_stripped
    ):
        tags.append("temporal_opener_strip")
    if language == "hu":
        article_trimmed = trim_articles(temporal_stripped, language=language)
        suffix_normalized = normalize_hu_subject_case_suffix(article_trimmed)
        if suffix_normalized != article_trimmed and normalize_claim_text(suffix_normalized) == cleaned_text:
            tags.append("suffix_normalization")
    return tags


def strip_trailing_subject_fillers(text: str, *, language: str) -> str:
    candidate = normalize_text(text).strip(TRIM_CHARS)
    trailing_terms = [*get_language_rules(language).filler_words, *SUBJECT_TIME_PATTERNS.get(language, ())]
    if not trailing_terms:
        return candidate
    pattern = re.compile(
        r"(?:\b(?:" + "|".join(re.escape(item) for item in trailing_terms) + r")\b[\s,;:-]*)+$",
        flags=re.IGNORECASE,
    )
    updated = pattern.sub("", candidate).strip(TRIM_CHARS)
    return updated or candidate


def strip_trailing_conjunctions_for_language(text: str, *, language: str) -> str:
    """Összes kötőszó a nyelvi szabályból (tisztítás; nem pattern-extract)."""
    candidate = normalize_text(text).strip(TRIM_CHARS)
    conjunctions = get_language_rules(language).conjunction_keywords
    if not conjunctions:
        return candidate
    pattern = re.compile(
        r"[\s,;:-]*\b(?:" + "|".join(re.escape(item) for item in conjunctions) + r")\b\s*$",
        flags=re.IGNORECASE,
    )
    updated = pattern.sub("", candidate).strip(TRIM_CHARS)
    return updated or candidate


def is_temporal_tail_token(token: str, *, language: str) -> bool:
    """Egy token időbeli-e (év, hónap, „jelenleg”, stb.)."""
    folded = fold_text(token.strip(TRIM_CHARS))
    if not folded:
        return False
    if YEAR_PATTERN.fullmatch(token.strip(TRIM_CHARS)):
        return True
    if folded in {fold_text(item) for item in get_language_rules(language).month_keywords}:
        return True
    if folded in {fold_text(item) for item in TEMPORAL_TAIL_KEYWORDS.get(language, ())}:
        return True
    if language == "hu" and re.fullmatch(r"(19|20)\d{2}(?:-?ben|-?ban)?", folded):
        return True
    if language == "hu" and (folded.endswith("ban") or folded.endswith("ben")):
        stem = re.sub(r"(?:ban|ben)$", "", folded).rstrip("a")
        months = {fold_text(item) for item in get_language_rules(language).month_keywords}
        return stem in months
    return False


def trim_temporal_tokens(text: str | None, *, language: str) -> str:
    """Végződő idő-tokenek levágása."""
    candidate = normalize_text(text or "").strip(TRIM_CHARS)
    if not candidate:
        return candidate
    tokens = candidate.split()
    while tokens and is_temporal_tail_token(tokens[-1], language=language):
        tokens.pop()
    if tokens and len(tokens) >= 2 and is_temporal_tail_token(tokens[-1], language=language):
        tokens.pop()
    return " ".join(tokens).strip(TRIM_CHARS)


def is_year_only(text: str | None) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and YEAR_PATTERN.fullmatch(normalized) is not None


def is_month_only(text: str | None, *, language: str) -> bool:
    normalized = fold_text(normalize_text(text))
    if not normalized:
        return False
    months = {fold_text(item) for item in get_language_rules(language).month_keywords}
    return normalized in months


def is_temporal_only_subject(text: str | None, *, language: str) -> bool:
    """Minden token időbeli (pl. „enero de 2025” több tokennel)."""
    t = normalize_claim_text(text)
    if not t:
        return False
    tokens = t.split()
    return bool(tokens) and all(is_temporal_tail_token(tok, language=language) for tok in tokens)


def _is_stopword_subject(text: str, *, language: str) -> bool:
    normalized = fold_text(normalize_text(text))
    if not normalized:
        return True
    return normalized in {fold_text(item) for item in get_language_rules(language).stopwords}


def sanitize_subject(text: str | None, *, language: str) -> str:
    """Subject cleanup: cikkek, fillerek, kötőszó leak, nyelvi kötőszavak, idő farok."""
    candidate = normalize_claim_text(text)
    candidate = strip_leading_source_phrase(candidate, language=language)
    candidate = strip_leading_weak_auxiliary(candidate, language=language)
    candidate = strip_leading_temporal_opener(candidate, language=language)
    neg_pattern = _TRAILING_NEGATION_TOKEN_RE.get(language)
    if neg_pattern is not None:
        candidate = neg_pattern.sub("", candidate).strip(TRIM_CHARS)
    candidate = trim_articles(candidate, language=language)
    candidate = trim_temporal_tokens(candidate, language=language)
    if language == "hu":
        candidate = normalize_hu_subject_case_suffix(candidate)
    candidate = strip_trailing_subject_fillers(candidate, language=language)
    candidate = trim_conjunction_leak(candidate, language=language)
    candidate = strip_trailing_conjunctions_for_language(candidate, language=language)
    return candidate.strip(TRIM_CHARS)


def sanitize_object(text: str | None, *, language: str) -> str:
    """Object cleanup: vezető kitöltők, cikkek, bizonytalanság farok, kötőszavak."""
    candidate = normalize_claim_text(text)
    if not candidate:
        return candidate
    for filler in OBJECT_LEADING_FILLERS.get(language, ()):
        candidate = re.sub(r"^\b" + re.escape(filler) + r"\b[\s,;:-]*", "", candidate, flags=re.IGNORECASE)
    candidate = trim_articles(candidate, language=language)
    for marker in UNCERTAINTY_MARKERS.get(language, ()):
        candidate = re.sub(r"[\s,;:-]+\b" + re.escape(marker) + r"\b\s*$", "", candidate, flags=re.IGNORECASE)
    candidate = trim_conjunction_leak(candidate, language=language)
    candidate = strip_trailing_conjunctions_for_language(candidate, language=language)
    return candidate.strip(TRIM_CHARS)


def is_bad_subject(text: str | None, *, language: str) -> bool:
    """Érvénytelen / használhatatlan subject a tisztítás után."""
    cleaned = sanitize_subject(text or "", language=language)
    if not cleaned:
        return True
    cleaned_fold = fold_text(cleaned)
    if _is_stopword_subject(cleaned, language=language):
        return True
    if cleaned_fold in BAD_SUBJECT_PRONOUNS.get(language, frozenset()):
        return True
    if cleaned_fold in BAD_SUBJECT_STANDALONE_ROLE_WORDS:
        return True
    if language == "es" and has_leading_weak_auxiliary(text or "", language=language):
        return True
    if language == "es" and _ES_CONJUGATED_VERB_SUBJECT_RE.match(cleaned):
        return True
    if language == "es" and _ES_PARTICIPLE_ONLY_SUBJECT_RE.match(cleaned):
        return True
    if is_year_only(cleaned):
        return True
    if is_month_only(cleaned, language=language):
        return True
    if is_temporal_only_subject(cleaned, language=language):
        return True
    return False


__all__ = [
    "SANITIZER_ARTICLES",
    "SANITIZER_CONJUNCTION_LEAK",
    "SUBJECT_SOURCE_PHRASE_PREFIXES",
    "SUBJECT_TEMPORAL_OPENER_PREFIXES",
    "has_leading_source_phrase",
    "has_leading_temporal_opener",
    "is_bad_subject",
    "is_month_only",
    "is_temporal_only_subject",
    "is_temporal_tail_token",
    "is_year_only",
    "normalize_hu_subject_case_suffix",
    "normalize_claim_text",
    "sanitize_object",
    "sanitize_subject",
    "subject_sanitizer_tags",
    "strip_leading_source_phrase",
    "strip_leading_temporal_opener",
    "strip_trailing_conjunctions_for_language",
    "strip_trailing_subject_fillers",
    "trim_articles",
    "trim_conjunction_leak",
    "trim_temporal_tokens",
]
