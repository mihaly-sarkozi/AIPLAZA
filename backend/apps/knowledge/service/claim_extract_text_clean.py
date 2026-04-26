"""ClaimExtractorV1: subject/object szeletek tisztítása, állítmányi tárgy szabályok, HU csonkítások."""
from __future__ import annotations

import re

from apps.knowledge.service.claim_extract_constants import (
    CLAUSE_BREAK_KEYWORDS,
    EN_RESPONSIBLE_COMPOUNDS,
    ES_RESPONSIBLE_COMPOUNDS,
    STATE_AUXILIARIES,
    STATE_COMPLEMENTS,
    STATE_OBJECT_PRONOUNS,
    STATE_OBJECT_TEMPORAL_PREFIXES,
    TEMPORAL_TAIL_KEYWORDS,
    TITLE_RELATION_PREDICATES,
    TRIM_CHARS,
)
from apps.knowledge.service.claim_extract_normalize import normalize_predicate, normalize_text
from apps.knowledge.service.claim_sanitizer import (
    is_month_only,
    is_temporal_tail_token,
    is_year_only,
    sanitize_object,
    sanitize_subject,
    strip_trailing_conjunctions_for_language,
    strip_trailing_subject_fillers,
    trim_articles,
    trim_temporal_tokens,
)
from apps.knowledge.service.language_rules import fold_text, get_language_rules


def leading_stopword_pattern(language: str) -> re.Pattern[str]:
    """Visszafoghatóság: cikk-regex a sanitizer listából."""
    from apps.knowledge.service.claim_sanitizer import SANITIZER_ARTICLES

    stopwords = sorted(
        (re.escape(item) for item in SANITIZER_ARTICLES.get(language, SANITIZER_ARTICLES["en"])),
        key=len,
        reverse=True,
    )
    return re.compile(r"^(?:" + "|".join(stopwords) + r")\b\s*", flags=re.IGNORECASE) if stopwords else re.compile(r"^$")


def strip_leading_stopwords(text: str, *, language: str) -> str:
    return trim_articles(text, language=language)


def strip_trailing_fillers(text: str, *, language: str) -> str:
    """Subject farok-fillerek: delegál a közös sanitizerre (egyetlen implementáció)."""
    return strip_trailing_subject_fillers(text, language=language)


def strip_trailing_conjunctions(text: str, *, language: str) -> str:
    """Nyelvi kötőszavak a chunk végén: delegál a sanitizerre."""
    return strip_trailing_conjunctions_for_language(text, language=language)


def trim_temporal_subject_tail(text: str, *, language: str) -> str:
    return trim_temporal_tokens(text, language=language)


def is_stopword_text(text: str | None, *, language: str) -> bool:
    normalized = fold_text(normalize_text(text))
    if not normalized:
        return True
    return normalized in {fold_text(item) for item in get_language_rules(language).stopwords}


def is_valid_subject_text(text: str | None, *, language: str) -> bool:
    from apps.knowledge.service.claim_sanitizer import is_bad_subject

    return not is_bad_subject(text, language=language)


def clean_subject_slice(text: str, *, language: str) -> str:
    return sanitize_subject(text, language=language)


def clean_object_slice(text: str, *, language: str) -> str:
    return sanitize_object(text, language=language)


def is_state_object_redundant_with_subject(
    object_text: str | None, subject_text: str | None, *, language: str
) -> bool:
    obj = normalize_text(object_text)
    subj = normalize_text(subject_text)
    if not obj or not subj:
        return False
    subj_f = fold_text(subj)
    obj_f = fold_text(obj)
    if obj_f == subj_f:
        return True
    subj_tokens = [
        t
        for t in re.findall(r"[\w\-]+", subj)
        if t and fold_text(t) not in {fold_text(a) for a in get_language_rules(language).article_stopwords}
    ]
    if not subj_tokens:
        return False
    obj_tokens = [t for t in re.findall(r"[\w\-]+", obj) if t]
    if len(obj_tokens) == 1 and obj_f in {fold_text(t) for t in subj_tokens}:
        return True
    return False


def should_drop_state_object(
    object_text: str | None,
    subject_text: str | None,
    *,
    language: str,
    state_predicate_fold: str | None = None,
) -> bool:
    candidate = normalize_text(object_text)
    if not candidate:
        return False
    if is_state_object_redundant_with_subject(candidate, subject_text, language=language):
        return True
    folded = fold_text(candidate)
    pronouns = STATE_OBJECT_PRONOUNS.get(language, set())
    if folded in pronouns:
        return True
    if any(folded.startswith(pronoun + " ") for pronoun in pronouns):
        return True
    tokens = folded.split()
    if not tokens:
        return False
    if len(tokens) == 1:
        state_auxiliaries = STATE_AUXILIARIES.get(language, set())
        state_complements = STATE_COMPLEMENTS.get(language, set())
        if tokens[0] in state_auxiliaries or tokens[0] in state_complements:
            return True
    if tokens[0] in STATE_OBJECT_TEMPORAL_PREFIXES.get(language, set()):
        if language == "en" and re.fullmatch(
            r"(?:in|on|at|before|after|since)\s+[A-Za-z]+\s+(19|20)\d{2}", candidate, flags=re.IGNORECASE
        ):
            return False
        if language == "en" and re.fullmatch(r"(?:in|on|at|before|after|since)\s+(19|20)\d{2}", candidate, flags=re.IGNORECASE):
            return False
        if language == "es" and re.fullmatch(r"en\s+(19|20)\d{2}", candidate, flags=re.IGNORECASE):
            if state_predicate_fold and "inactiv" in state_predicate_fold:
                return False
        if len(tokens) <= 2:
            return True
        if len(tokens) >= 2 and (is_year_only(tokens[1]) or is_month_only(tokens[1], language=language)):
            if len(tokens) >= 3 and is_year_only(tokens[2]):
                return False
            return True
    return False


def trim_hu_vezetoje_leading_subject(text: str) -> str:
    s = normalize_text(text)
    m = re.match(r"^(.+?)\s+\b(a|az)\s+.+$", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(TRIM_CHARS)
    return s


def trim_hu_felelt_leading_subject(text: str) -> str:
    s = normalize_text(text)
    m = re.match(r"^(.+?)\s+(?:korábban|korabban)\s+", s, flags=re.IGNORECASE)
    if m:
        s = m.group(1).strip(TRIM_CHARS)
    m2 = re.match(r"^(.+?)\s+\b(a|az)\s+.+$", s, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip(TRIM_CHARS)
    return s


def normalize_predicate_display(
    raw_predicate: str, *, text: str, language: str, pred_start: int, pred_end: int
) -> str:
    n = normalize_text(raw_predicate)
    n_fold = normalize_predicate(n)
    if language == "en":
        for compound in EN_RESPONSIBLE_COMPOUNDS:
            if n_fold == normalize_predicate(compound):
                span = normalize_text(text[pred_start:pred_end])
                m = re.search(r"\bresponsible\b", span, flags=re.IGNORECASE)
                if m:
                    return m.group(0)
                return "responsible"
        return raw_predicate
    if language == "es":
        for compound in ES_RESPONSIBLE_COMPOUNDS:
            if n_fold == normalize_predicate(compound):
                span = normalize_text(text[pred_start:pred_end])
                m = re.search(r"\bresponsable\b", span, flags=re.IGNORECASE)
                if m:
                    return m.group(0)
                return "responsable"
        return raw_predicate
    return raw_predicate


def trim_clause_break(text: str, *, language: str) -> str:
    candidate = normalize_text(text).strip(TRIM_CHARS)
    if not candidate:
        return candidate
    for keyword in CLAUSE_BREAK_KEYWORDS.get(language, ()):
        match = re.search(r"\s+\b" + re.escape(keyword) + r"\b\s+", candidate, flags=re.IGNORECASE)
        if match is not None:
            candidate = candidate[: match.start()].strip(TRIM_CHARS)
            break
    candidate = re.split(r"\s*[;:]\s*", candidate, maxsplit=1)[0].strip(TRIM_CHARS)
    return candidate


def find_local_clause_start(text: str, predicate_idx: int | None) -> int:
    if predicate_idx is None:
        return 0
    separators = [text.rfind(marker, 0, predicate_idx) for marker in (",", ";", ":")]
    last_separator = max(separators, default=-1)
    return last_separator + 1 if last_separator >= 0 else 0


def build_claim_text(text: str, subject_text: str, predicate: str, object_text: str | None) -> str:
    spo_text = " ".join(part for part in [subject_text, predicate, object_text] if part).strip()
    return spo_text or text.strip()


def should_prefer_relation_title_object(
    predicate: str | None,
    remainder: str | None,
    *,
    language: str,
) -> bool:
    normalized_predicate = normalize_predicate(predicate)
    if normalized_predicate not in {fold_text(item) for item in TITLE_RELATION_PREDICATES.get(language, set())}:
        return False
    if not remainder:
        return True
    lowered_remainder = normalize_predicate(remainder)
    if not lowered_remainder:
        return True
    leading_markers = {
        *[fold_text(item) for item in TEMPORAL_TAIL_KEYWORDS.get(language, ())],
        *[fold_text(item) for item in CLAUSE_BREAK_KEYWORDS.get(language, ())],
    }
    first_token = lowered_remainder.split()[0]
    return first_token in leading_markers


def build_relation_title_object(pre_predicate_object: str, predicate: str) -> str:
    normalized_object = normalize_text(pre_predicate_object)
    if not normalized_object:
        return normalize_text(predicate)
    return normalized_object
