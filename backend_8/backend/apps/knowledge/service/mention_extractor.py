from __future__ import annotations

import re
import unicodedata

from apps.knowledge.domain.mention import Mention, MentionType
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.language_rules import detect_language, get_language_rules, resolve_language

TOKEN_PATTERN = re.compile(
    r"[0-9A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+(?:[._/-][0-9A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+)*",
    flags=re.UNICODE,
)
WHITESPACE_PATTERN = re.compile(r"\s+")
MULTIWORD_GAP_PATTERN = re.compile(r"^\s+(?:de\s+|of\s+|a\s+|az\s+|the\s+|el\s+|la\s+)?$", flags=re.IGNORECASE)
CONNECTOR_WORDS = {"de", "del", "of"}


def _normalize_text(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", value.strip().lower())


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _is_capitalized_token(token: str) -> bool:
    return bool(token) and token[0].isalpha() and token[0].isupper()


def _is_numeric_dominant(token: str) -> bool:
    digits = sum(char.isdigit() for char in token)
    letters = sum(char.isalpha() for char in token)
    return digits > 0 and digits >= max(letters, 1)


def _token_matches_keyword(token: str, keyword: str, *, language: str | None = None) -> bool:
    normalized_token = _normalize_text(token)
    normalized_keyword = _normalize_text(keyword)
    if normalized_token == normalized_keyword:
        return True
    if resolve_language(language=language) != "hu":
        return False
    folded_token = _fold_text(normalized_token)
    folded_keyword = _fold_text(normalized_keyword)
    return len(folded_keyword) >= 4 and folded_token.startswith(folded_keyword)


def _matches_any_keyword(token: str, keywords: set[str] | tuple[str, ...], *, language: str | None = None) -> bool:
    return any(_token_matches_keyword(token, keyword, language=language) for keyword in keywords)


def _is_stopword(token: str, *, language: str) -> bool:
    rules = get_language_rules(language)
    return _fold_text(token) in {_fold_text(item) for item in rules.stopwords}


def _is_repeated_token_noise(surface_text: str) -> bool:
    tokens = [_fold_text(token) for token in surface_text.split() if token]
    if len(tokens) < 2:
        return False
    unique_tokens = {token for token in tokens if token}
    if len(unique_tokens) == 1:
        return True
    if len(tokens) >= 3 and len(unique_tokens) <= 2:
        return True
    return False


def _has_location_or_module_context(parts: tuple[str, ...], *, language: str | None = None) -> bool:
    rules = get_language_rules(language)
    context_keywords = {
        *[_normalize_text(item) for item in rules.location_keywords],
        *[_normalize_text(item) for item in rules.module_keywords],
    }
    return any(part in context_keywords for part in parts)


def _clean_surface_text(surface_text: str, char_start: int, char_end: int, *, language: str) -> tuple[str, int, int] | None:
    text = surface_text
    start = char_start
    end = char_end

    while True:
        match = re.match(r"^\s*([0-9A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+)\b(\s+)?", text, flags=re.UNICODE)
        if match is None:
            break
        token = match.group(1)
        remainder = text[match.end() :]
        is_single_token = not remainder.strip()
        if is_single_token and (_is_stopword(token, language=language) or len(_normalize_text(token)) <= 2):
            return None
        if not is_single_token and _is_stopword(token, language=language):
            start += match.end()
            text = remainder
            continue
        break

    text = text.strip()
    if not text:
        return None

    normalized_text = _normalize_text(text)
    if not normalized_text:
        return None

    if _is_stopword(normalized_text, language=language):
        return None

    if len(normalized_text) <= 2 and len(normalized_text.split()) == 1:
        return None

    if _is_repeated_token_noise(text):
        return None

    end = start + len(text)
    return text, start, end


def _classify_mention(surface_text: str, *, language: str | None = None) -> str:
    parts = tuple(_normalize_text(surface_text).split())
    rules = get_language_rules(language)
    raw_parts = tuple(surface_text.split())
    if any(_matches_any_keyword(part, rules.company_keywords, language=language) for part in parts):
        return MentionType.COMPANY.value
    if any(_matches_any_keyword(part, rules.location_keywords, language=language) for part in parts):
        return MentionType.LOCATION.value
    if any(_matches_any_keyword(part, rules.module_keywords, language=language) for part in parts):
        return MentionType.MODULE.value
    if any(_matches_any_keyword(part, rules.software_keywords, language=language) for part in parts):
        return MentionType.SOFTWARE.value
    if any(_matches_any_keyword(part, rules.feature_keywords, language=language) for part in parts):
        return MentionType.FEATURE.value
    if any(_matches_any_keyword(part, rules.policy_keywords, language=language) for part in parts):
        return MentionType.POLICY.value
    if any(_matches_any_keyword(part, rules.process_keywords, language=language) for part in parts):
        return MentionType.PROCESS.value
    if (
        len(raw_parts) >= 2
        and all(_is_capitalized_token(part) for part in raw_parts if part)
        and not _has_location_or_module_context(parts, language=language)
        and not _is_repeated_token_noise(surface_text)
    ):
        return MentionType.PERSON.value
    if _is_numeric_dominant(surface_text):
        return MentionType.OBJECT.value
    return MentionType.UNKNOWN.value


def _build_mention(sentence: Sentence, surface_text: str, char_start: int, char_end: int, *, language: str) -> Mention:
    cleaned = _clean_surface_text(surface_text, char_start, char_end, language=language)
    if cleaned is None:
        return None
    cleaned_text, cleaned_start, cleaned_end = cleaned
    normalized_text = _normalize_text(cleaned_text)
    token_count = len(cleaned_text.split())
    confidence = 0.7 if token_count > 1 and all(_is_capitalized_token(part) for part in cleaned_text.split()) else 0.5
    return Mention(
        tenant=sentence.tenant,
        corpus_uuid=sentence.corpus_uuid,
        source_id=sentence.source_id,
        document_id=sentence.document_id,
        sentence_id=sentence.id,
        mention_type=_classify_mention(cleaned_text, language=language),
        text_content=cleaned_text,
        normalized_value=normalized_text,
        char_start=cleaned_start,
        char_end=cleaned_end,
        confidence=confidence,
        metadata={
            "extractor": "MentionExtractor",
            "token_count": token_count,
            "language": language,
        },
    )


def _mention_priority(mention: Mention) -> tuple[int, int, int]:
    mention_type = str(mention.mention_type or MentionType.UNKNOWN.value)
    type_priority = {
        MentionType.LOCATION.value: 0,
        MentionType.COMPANY.value: 1,
        MentionType.MODULE.value: 2,
        MentionType.SOFTWARE.value: 3,
        MentionType.PERSON.value: 4,
        MentionType.PROCESS.value: 5,
        MentionType.POLICY.value: 6,
        MentionType.FEATURE.value: 7,
        MentionType.OBJECT.value: 8,
        MentionType.UNKNOWN.value: 9,
    }
    length = mention.char_end - mention.char_start
    return (type_priority.get(mention_type, 99), -length, mention.char_start)


def _deduplicate_mentions(mentions: list[Mention]) -> list[Mention]:
    if not mentions:
        return []
    kept: list[Mention] = []
    for mention in sorted(mentions, key=_mention_priority):
        is_shadowed = False
        for existing in kept:
            if (
                mention.char_start >= existing.char_start
                and mention.char_end <= existing.char_end
                and mention.text_content != existing.text_content
            ):
                same_prefix = existing.normalized_text.startswith(mention.normalized_text)
                if same_prefix or str(existing.mention_type or "") == MentionType.LOCATION.value:
                    is_shadowed = True
                    break
        if not is_shadowed:
            kept.append(mention)
    return sorted(kept, key=lambda item: (item.char_start, item.char_end, item.text_content))


def _target_noun_keywords(language: str) -> set[str]:
    rules = get_language_rules(language)
    return {
        *rules.software_keywords,
        *rules.module_keywords,
        *rules.feature_keywords,
        *rules.policy_keywords,
        *rules.process_keywords,
        *rules.location_keywords,
    }


def _iter_keyword_phrase_mentions(sentence: Sentence, *, language: str) -> list[Mention]:
    text = sentence.text_content or ""
    mentions: list[Mention] = []
    tokens = list(TOKEN_PATTERN.finditer(text))
    target_keywords = _target_noun_keywords(language)
    predicate_keywords = get_language_rules(language).predicate_keywords
    for idx, match in enumerate(tokens):
        token_text = match.group(0)
        if not _matches_any_keyword(token_text, target_keywords, language=language):
            continue
        start_idx = idx
        while start_idx > 0:
            previous = tokens[start_idx - 1]
            gap = text[previous.end() : tokens[start_idx].start()]
            if not MULTIWORD_GAP_PATTERN.match(gap):
                break
            previous_text = previous.group(0)
            candidate = _normalize_text(previous_text)
            if _is_numeric_dominant(previous_text):
                start_idx -= 1
                continue
            if _matches_any_keyword(previous_text, predicate_keywords, language=language):
                break
            if _is_stopword(previous_text, language=language):
                start_idx -= 1
                continue
            if _matches_any_keyword(previous_text, target_keywords, language=language):
                break
            if len(candidate) > 1:
                start_idx -= 1
                continue
            break
        end_idx = idx + 1
        include_connector_phrase = False
        if end_idx < len(tokens):
            next_token = tokens[end_idx].group(0)
            include_connector_phrase = _fold_text(next_token) in CONNECTOR_WORDS
        while include_connector_phrase and end_idx < len(tokens):
            current = tokens[end_idx]
            current_text = current.group(0)
            gap = text[tokens[end_idx - 1].end() : current.start()]
            if gap.strip():
                break
            if _matches_any_keyword(current_text, predicate_keywords, language=language):
                break
            end_idx += 1
            if end_idx >= len(tokens):
                break
            next_token = tokens[end_idx].group(0)
            if _matches_any_keyword(next_token, predicate_keywords, language=language):
                break
        span_start = tokens[start_idx].start()
        span_end = tokens[end_idx - 1].end()
        mention = _build_mention(sentence, text[span_start:span_end], span_start, span_end, language=language)
        if mention is not None:
            mentions.append(mention)
    return mentions


class MentionExtractor:
    def extract(self, sentence: Sentence, language: str | None = None) -> list[Mention]:
        resolved_language = detect_language(
            sentence.text_content,
            preferred_language=resolve_language(
                text=sentence.text_content,
                language=sentence.metadata.get("language") or sentence.metadata.get("language_tag") or language,
            ),
        )
        text = sentence.text_content or ""
        tokens = list(TOKEN_PATTERN.finditer(text))
        mentions: list[Mention] = _iter_keyword_phrase_mentions(sentence, language=resolved_language)
        seen_spans = {(item.char_start, item.char_end, item.text_content) for item in mentions}
        idx = 0

        while idx < len(tokens):
            match = tokens[idx]
            token_text = match.group(0)

            if _is_capitalized_token(token_text):
                start_idx = idx
                end_idx = idx + 1
                while end_idx < len(tokens):
                    previous = tokens[end_idx - 1]
                    current = tokens[end_idx]
                    gap = text[previous.end() : current.start()]
                    if gap.strip():
                        break
                    current_text = current.group(0)
                    if _is_numeric_dominant(current_text):
                        end_idx += 1
                        continue
                    if not _is_capitalized_token(current_text):
                        break
                    end_idx += 1

                span_start = tokens[start_idx].start()
                span_end = tokens[end_idx - 1].end()
                key = (span_start, span_end, text[span_start:span_end])
                if key not in seen_spans:
                    mention = _build_mention(
                        sentence,
                        text[span_start:span_end],
                        span_start,
                        span_end,
                        language=resolved_language,
                    )
                    if mention is not None:
                        mentions.append(mention)
                        seen_spans.add((mention.char_start, mention.char_end, mention.text_content))
                idx = end_idx
                continue

            if _is_numeric_dominant(token_text):
                key = (match.start(), match.end(), token_text)
                if key not in seen_spans:
                    mention = _build_mention(
                        sentence,
                        token_text,
                        match.start(),
                        match.end(),
                        language=resolved_language,
                    )
                    if mention is not None:
                        mentions.append(mention)
                        seen_spans.add((mention.char_start, mention.char_end, mention.text_content))

            idx += 1

        return _deduplicate_mentions(mentions)


def debug_print(sentence: Sentence, mentions: list[Mention], language: str | None = None) -> None:
    sentence_text = getattr(sentence, "text", sentence.text_content)
    resolved_language = resolve_language(
        text=sentence.text_content,
        language=language or sentence.metadata.get("language") or sentence.metadata.get("language_tag"),
    )
    print(f"[MENTION DEBUG] language={resolved_language} sentence={sentence_text}")
    for mention in mentions:
        print(f"  mention={mention.debug_repr()}")


__all__ = ["MentionExtractor", "debug_print"]
