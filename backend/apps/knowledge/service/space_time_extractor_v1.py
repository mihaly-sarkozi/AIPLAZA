from __future__ import annotations

import re

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.language_rules import detect_language, fold_text, get_language_rules, resolve_language

TIME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hu": (
        "ma",
        "tegnap",
        "holnap",
        "jelenleg",
        "most",
        "2024",
        "2025",
        "2026",
        "januar",
        "februar",
        "marcius",
        "aprilis",
        "majus",
        "junius",
        "julius",
        "augusztus",
        "szeptember",
        "oktober",
        "november",
        "december",
        "ota",
        "elott",
        "utan",
        "létrejött",
        "módosult",
    ),
    "en": (
        "today",
        "yesterday",
        "tomorrow",
        "currently",
        "now",
        "since",
        "before",
        "after",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "created",
        "updated",
    ),
    "es": (
        "hoy",
        "ayer",
        "mañana",
        "manana",
        "actualmente",
        "ahora",
        "desde",
        "antes",
        "después",
        "despues",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
        "creado",
        "actualizado",
    ),
}

SPACE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hu": ("iroda", "budapesti", "telephely", "helyszín", "helyszin", "ország", "orszag", "város", "varos"),
    "en": ("office", "location", "site", "country", "city"),
    "es": ("oficina", "ubicación", "ubicacion", "sede", "país", "pais", "ciudad"),
}

CURRENT_TIME_KEYWORDS = {
    "hu": ("ma", "jelenleg", "most"),
    "en": ("today", "currently", "now"),
    "es": ("hoy", "actualmente", "ahora"),
}

OPEN_TIME_KEYWORDS = {
    "hu": ("óta", "ota"),
    "en": ("since",),
    "es": ("desde",),
}

BOUNDED_TIME_KEYWORDS = {
    "hu": ("előtt", "elott", "után", "utan", "korábban", "korabban"),
    "en": ("before", "after", "earlier", "previously"),
    "es": ("antes", "después", "despues", "anteriormente"),
}

EVENT_TIME_KEYWORDS = {
    "hu": ("létrejött", "módosult", "created", "updated"),
    "en": ("created", "updated", "létrejött", "módosult"),
    "es": ("creado", "actualizado", "létrejött", "módosult"),
}

MONTH_KEYWORDS = {
    "hu": (
        "január",
        "február",
        "március",
        "április",
        "május",
        "június",
        "július",
        "augusztus",
        "szeptember",
        "október",
        "november",
        "december",
        "januar",
        "februar",
        "marcius",
        "aprilis",
        "majus",
        "junius",
        "julius",
        "oktober",
    ),
    "en": (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ),
    "es": (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
}

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüűÑñ]+", flags=re.UNICODE)
HU_YEAR_SUFFIX_PATTERN = re.compile(r"\b((?:19|20)\d{2})(?:-?ben|-?ban)\b", flags=re.IGNORECASE)


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _sentence_text(sentence: Sentence) -> str:
    return getattr(sentence, "text", sentence.text_content or "")


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(r"\b" + re.escape(fold_text(keyword)) + r"\b", fold_text(text), flags=re.IGNORECASE) is not None


def _find_first_keyword(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        if _contains_keyword(text, keyword):
            return keyword
    return None


def _extract_month_or_year_phrase(text: str, *, language: str) -> str | None:
    months = sorted((re.escape(item) for item in get_language_rules(language).month_keywords), key=len, reverse=True)
    if months:
        if language == "hu":
            year_first_pattern = re.compile(
                r"\b((?:19|20)\d{2}\s+(?:" + "|".join(months) + r")(?:[a-záéíóöőúüű]+)?)\b",
                flags=re.IGNORECASE,
            )
            year_first_match = year_first_pattern.search(text)
            if year_first_match:
                return " ".join(year_first_match.group(1).strip(" ,;:-.").split())
        pattern = re.compile(
            r"\b(?:" + "|".join(months) + r")\b(?:\s+de)?(?:\s+\d{4})?",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return " ".join(match.group(0).strip(" ,;:-.").split())
    return None


def _extract_year_with_marker(text: str, *, language: str) -> str | None:
    raw_text = " ".join(str(text or "").strip().split())
    lowered = fold_text(raw_text)
    marker_patterns = {
        "hu": (r"\b(?:evben|évben|ota|óta|elott|előtt|utan|után)\s+((?:19|20)\d{2})\b",),
        "en": (r"\b(?:in|before|after|since)\s+((?:19|20)\d{2})\b",),
        "es": (r"\b(?:en|antes|despues|después|desde)\s+((?:19|20)\d{2})\b",),
    }
    for pattern in marker_patterns.get(language, ()):
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    if language == "hu":
        match = HU_YEAR_SUFFIX_PATTERN.search(raw_text)
        if match:
            return match.group(1)
    return None


def _extract_bounded_time_phrase(text: str, *, language: str) -> str | None:
    raw_text = " ".join(str(text or "").strip().split())
    if not raw_text:
        return None
    months = sorted((re.escape(item) for item in get_language_rules(language).month_keywords), key=len, reverse=True)
    if language == "en":
        patterns = [
            re.compile(r"\b(before|after)\s+((?:" + "|".join(months) + r")(?:\s+\d{4})?)\b", flags=re.IGNORECASE) if months else None,
            re.compile(r"\b(before|after)\s+(\d{4})\b", flags=re.IGNORECASE),
            re.compile(r"\b(previously|earlier)\b", flags=re.IGNORECASE),
        ]
    elif language == "es":
        patterns = [
            re.compile(r"\b(antes)\s+de\s+((?:" + "|".join(months) + r")(?:\s+de\s+\d{4})?)\b", flags=re.IGNORECASE) if months else None,
            re.compile(r"\b(en)\s+(\d{4})\b", flags=re.IGNORECASE),
            re.compile(r"\b(anteriormente)\b", flags=re.IGNORECASE),
        ]
    else:
        patterns = [
            re.compile(r"\b(korábban|korabban)\b", flags=re.IGNORECASE),
            re.compile(r"\b((?:19|20)\d{2})(?:-?ben|-?ban)\b", flags=re.IGNORECASE),
        ]
    for pattern in patterns:
        if pattern is None:
            continue
        match = pattern.search(raw_text)
        if match:
            return " ".join(match.group(0).strip(" ,;:-.").split())
    return None


def _extract_current_keyword(text: str, *, language: str) -> str | None:
    return _find_first_keyword(text, CURRENT_TIME_KEYWORDS.get(language, ()))


def _folded_with_index_map(text: str) -> tuple[str, list[int]]:
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


def _find_predicate_span(text: str, predicate: str | None) -> tuple[int, int] | None:
    normalized_text = " ".join(str(text or "").split())
    normalized_predicate = " ".join(str(predicate or "").split())
    if not normalized_text or not normalized_predicate:
        return None
    folded_text, index_map = _folded_with_index_map(normalized_text)
    folded_predicate = fold_text(normalized_predicate)
    match = re.search(r"\b" + re.escape(folded_predicate) + r"\b", folded_text)
    if match is None:
        return None
    start, end = match.span()
    return index_map[start], index_map[end - 1] + 1


def _extract_predicate_clause(text: str, predicate: str | None) -> str:
    normalized_text = " ".join(str(text or "").split())
    span = _find_predicate_span(normalized_text, predicate)
    if span is None:
        return normalized_text
    start, end = span
    left_break = max(normalized_text.rfind(marker, 0, start) for marker in (",", ";", ":"))
    right_candidates = [normalized_text.find(marker, end) for marker in (",", ";", ":")]
    right_break = min((idx for idx in right_candidates if idx != -1), default=len(normalized_text))
    clause = normalized_text[left_break + 1 : right_break].strip(" ,;:-.")
    return clause or normalized_text


def _extract_context_snippet(text: str, keyword: str) -> str:
    match = re.search(r"\b" + re.escape(keyword) + r"\b", text, flags=re.IGNORECASE)
    if match is None:
        return text.strip()
    left = max(0, match.start() - 24)
    right = min(len(text), match.end() + 24)
    snippet = text[left:right].strip(" ,;:-.")
    return " ".join(snippet.split()) or keyword


def _clean_space_phrase(value: str | None) -> str | None:
    candidate = " ".join(str(value or "").strip(" ,;:-.()").split())
    if not candidate:
        return None
    candidate = re.sub(r"^(?:in|at|on|en|a|az|the|el|la|los|las)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\b(?:currently|jelenleg|actualmente)\b", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+", " ", candidate).strip(" ,;:-.")
    return candidate or None


def _mention_text(mention: Mention) -> str:
    return str(mention.surface_text or mention.normalized_text or "").strip()


def _mention_normalized_text(mention: Mention) -> str:
    return str(mention.normalized_text or mention.surface_text or "").strip()


def _extract_space_from_location_mentions(mentions: list[Mention] | None, *, language: str) -> str | None:
    if not mentions:
        return None
    for mention in mentions:
        if str(mention.mention_type or "") != "location":
            continue
        normalized = _clean_space_phrase(_mention_normalized_text(mention))
        surface = _clean_space_phrase(_mention_text(mention))
        candidate = surface or normalized
        if not candidate:
            continue
        if _extract_space_phrase(candidate, language=language):
            return candidate
    return None


def _extract_space_phrase(text: str | None, *, language: str) -> str | None:
    candidate = _clean_space_phrase(text)
    if not candidate:
        return None
    tokens = TOKEN_PATTERN.findall(candidate)
    if not tokens:
        return None
    keyword_set = {fold_text(item) for item in SPACE_KEYWORDS.get(language, ())}
    for idx, token in enumerate(tokens):
        folded = fold_text(token)
        if folded not in keyword_set:
            continue
        if language == "hu":
            if folded.endswith("i") and idx + 1 < len(tokens) and fold_text(tokens[idx + 1]) in keyword_set:
                return _clean_space_phrase(f"{token} {tokens[idx + 1]}")
            if idx > 0:
                previous = tokens[idx - 1]
                if previous[:1].isupper() or fold_text(previous).endswith("i"):
                    return _clean_space_phrase(f"{previous} {token}")
            return _clean_space_phrase(token)
        if language == "en":
            if idx > 0 and tokens[idx - 1][:1].isupper():
                return _clean_space_phrase(f"{tokens[idx - 1]} {token}")
            if idx + 2 < len(tokens) and fold_text(tokens[idx + 1]) == "of" and tokens[idx + 2][:1].isupper():
                return _clean_space_phrase(f"{token} {tokens[idx + 1]} {tokens[idx + 2]}")
            return _clean_space_phrase(token)
        if language == "es":
            if idx + 2 < len(tokens) and fold_text(tokens[idx + 1]) == "de" and tokens[idx + 2][:1].isupper():
                return _clean_space_phrase(f"{token} {tokens[idx + 1]} {tokens[idx + 2]}")
            if idx > 0 and tokens[idx - 1][:1].isupper():
                return _clean_space_phrase(f"{tokens[idx - 1]} {token}")
            return _clean_space_phrase(token)
    return None


class SpaceTimeExtractorV1:
    def extract(
        self,
        claim: Claim,
        sentence: Sentence,
        language: str | None = None,
        mentions: list[Mention] | None = None,
    ) -> SpaceTimeFrame:
        text = _sentence_text(sentence)
        resolved_language = detect_language(
            " ".join(part for part in [text, claim.claim_text, claim.predicate] if part),
            preferred_language=resolve_language(
                text=" ".join(part for part in [text, claim.claim_text, claim.predicate] if part),
                language=sentence.metadata.get("language") or claim.metadata.get("language") or language,
            ),
        )
        lowered_text = _normalize_text(text)
        object_text = str(claim.object_text or "").strip()
        predicate_clause = _extract_predicate_clause(text, claim.predicate)
        lowered_clause = _normalize_text(predicate_clause)

        time_mode = "unknown"
        time_value: str | None = None
        time_precision: str | None = None
        time_confidence = 0.5
        space_mode = "unknown"
        space_value: str | None = None
        space_precision: str | None = None
        space_confidence = 0.5
        overall_confidence = 0.5

        claim_type = str(claim.claim_type or "other").strip().lower()
        if claim_type in {"identifier", "stable_descriptor"}:
            time_mode = "zero_time"
            space_mode = "irrelevant"
            time_confidence = 0.6
            space_confidence = 0.6
            overall_confidence = 0.6
        elif claim_type == "state":
            time_mode = "current"
            time_confidence = 0.6
            overall_confidence = 0.6
        elif claim_type == "event":
            time_mode = "event"
            time_confidence = 0.7
            overall_confidence = 0.7
        elif claim_type == "rule_procedure":
            time_mode = "zero_time"
            space_mode = "irrelevant"
            time_confidence = 0.6
            space_confidence = 0.6
            overall_confidence = 0.6

        local_time_context = object_text or lowered_clause
        local_bounded_keyword = _find_first_keyword(
            local_time_context, BOUNDED_TIME_KEYWORDS.get(resolved_language, ())
        )
        current_keyword = _find_first_keyword(local_time_context, CURRENT_TIME_KEYWORDS.get(resolved_language, ()))
        if current_keyword is None and local_bounded_keyword is None:
            current_keyword = _find_first_keyword(lowered_text, CURRENT_TIME_KEYWORDS.get(resolved_language, ()))
        event_keyword = _find_first_keyword(object_text or lowered_clause, EVENT_TIME_KEYWORDS.get(resolved_language, ())) or _find_first_keyword(
            lowered_text, EVENT_TIME_KEYWORDS.get(resolved_language, ())
        )
        open_keyword = _find_first_keyword(object_text or lowered_clause, OPEN_TIME_KEYWORDS.get(resolved_language, ())) or _find_first_keyword(
            lowered_text, OPEN_TIME_KEYWORDS.get(resolved_language, ())
        )
        bounded_keyword = local_bounded_keyword or _find_first_keyword(lowered_text, BOUNDED_TIME_KEYWORDS.get(resolved_language, ()))
        month_keyword = _find_first_keyword(object_text or lowered_clause, MONTH_KEYWORDS.get(resolved_language, ())) or _find_first_keyword(
            lowered_text, MONTH_KEYWORDS.get(resolved_language, ())
        )
        year_with_marker = (
            _extract_year_with_marker(object_text, language=resolved_language)
            or _extract_year_with_marker(predicate_clause, language=resolved_language)
            or _extract_year_with_marker(text, language=resolved_language)
        )

        precise_time_value = (
            _extract_month_or_year_phrase(object_text, language=resolved_language)
            or _extract_month_or_year_phrase(predicate_clause, language=resolved_language)
            or _extract_month_or_year_phrase(text, language=resolved_language)
        )
        bounded_time_phrase = (
            _extract_bounded_time_phrase(object_text, language=resolved_language)
            or _extract_bounded_time_phrase(predicate_clause, language=resolved_language)
            or _extract_bounded_time_phrase(text, language=resolved_language)
        )

        if current_keyword is not None:
            time_mode = "current"
            time_value = current_keyword
            time_precision = "relative"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)
        elif event_keyword is not None:
            time_mode = "event"
            time_value = precise_time_value or event_keyword
            time_precision = "lexical_event"
            time_confidence = max(time_confidence, 0.7)
            overall_confidence = max(overall_confidence, 0.7)
        elif open_keyword is not None:
            time_mode = "open"
            time_value = _extract_context_snippet(text, open_keyword)
            time_precision = "relative"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)
        elif bounded_keyword is not None:
            time_mode = "bounded"
            time_value = bounded_time_phrase or precise_time_value or bounded_keyword
            time_precision = "relative"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)
        elif precise_time_value is not None:
            time_mode = "bounded"
            time_value = precise_time_value
            time_precision = "month" if any(_contains_keyword(precise_time_value, item) for item in MONTH_KEYWORDS.get(resolved_language, ())) else "year"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)
        elif year_with_marker is not None:
            time_mode = "bounded"
            time_value = year_with_marker
            time_precision = "year"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)
        elif month_keyword is not None:
            time_mode = "bounded"
            time_value = precise_time_value or month_keyword
            time_precision = "month"
            time_confidence = max(time_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)

        location_mention_space = _extract_space_from_location_mentions(mentions, language=resolved_language)
        space_value = location_mention_space
        if space_value is None:
            space_value = (
                _extract_space_phrase(claim.subject_text, language=resolved_language)
                or _extract_space_phrase(object_text, language=resolved_language)
                or _extract_space_phrase(text, language=resolved_language)
            )
        space_keyword = _find_first_keyword(lowered_text, SPACE_KEYWORDS.get(resolved_language, ()))
        if space_value is not None:
            space_mode = "bounded"
            space_precision = "mention" if location_mention_space is not None else "entity_phrase"
            space_confidence = max(space_confidence, 0.75 if space_precision == "mention" else 0.7)
            overall_confidence = max(overall_confidence, space_confidence)
        elif space_keyword is not None:
            space_mode = "bounded"
            space_value = _extract_context_snippet(text, space_keyword)
            space_precision = "sentence_snippet"
            space_confidence = max(space_confidence, 0.6)
            overall_confidence = max(overall_confidence, 0.6)

        return SpaceTimeFrame(
            claim_id=claim.claim_id,
            sentence_id=sentence.id,
            source_id=sentence.source_id or claim.source_id or None,
            language=resolved_language or "unknown",
            time_mode=time_mode,
            time_value=time_value,
            time_precision=time_precision,
            time_confidence=time_confidence,
            space_mode=space_mode,
            space_value=space_value,
            space_precision=space_precision,
            space_confidence=space_confidence,
            overall_confidence=overall_confidence,
        )

    @staticmethod
    def debug_print(claim: Claim, frame: SpaceTimeFrame) -> None:
        debug_print(claim, frame)


def debug_print(claim: Claim, frame: SpaceTimeFrame) -> None:
    print("[SPACE-TIME DEBUG]")
    print("  claim=", claim.debug_repr())
    print("  frame=", frame.debug_repr())


__all__ = ["SpaceTimeExtractorV1", "debug_print"]
