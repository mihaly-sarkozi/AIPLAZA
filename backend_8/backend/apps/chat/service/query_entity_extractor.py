from __future__ import annotations

import re

from apps.chat.service.chat_text_utils import dedupe_keep_order, fold_lexicon_token, fold_text
from shared.text.language_lexicon import SUPPORTED_LEXICON_LANGUAGES, get_lexicon_terms


class QueryEntityExtractor:
    ENTITY_TOKEN_STOPWORDS = {
        fold_lexicon_token(token)
        for language_code in SUPPORTED_LEXICON_LANGUAGES
        for token in get_lexicon_terms(language_code, "entity_stopwords")
    }
    ENTITY_HINT_STOPWORDS = {
        fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "entity_hint_stopwords")
    }
    ENTITY_DESCRIPTOR_TERMS = {
        fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "descriptor_terms")
    }
    ENTITY_SUFFIXES = get_lexicon_terms("hu", "entity_suffixes", include_fallback=False)
    ENTITY_STOPWORDS = {
        token.capitalize()
        for token in get_lexicon_terms("hu", "question_words", include_fallback=False)
    } | {"Mutasd", "Mondd", "Keresd", "Van", "Volt", "Lesz", "A", "Az", "És", "Vagy"}
    CAP_SEQ_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)*\b")

    @classmethod
    def normalize_entity_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        lower = raw.lower()
        for suffix in sorted(cls.ENTITY_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                candidate = raw[: len(raw) - len(suffix)]
                if candidate and candidate[:1].isalpha():
                    return candidate
        return raw

    @classmethod
    def extract_entity_candidates(cls, question: str) -> list[str]:
        out: list[str] = []
        text = str(question or "")
        cls._append_explicit_pairs(out, text)
        cls._append_capitalized_sequences(out, text)
        cls._append_lowercase_pairs(out, text)
        return dedupe_keep_order(out)

    @classmethod
    def strong_entity_candidates(cls, query_profile: dict) -> list[str]:
        out: list[str] = []
        lexical_hints = [str(item or "").strip() for item in (query_profile.get("lexical_focus_terms") or [])]
        for raw in query_profile.get("entity_candidates") or []:
            normalized = cls._strong_candidate_from_raw(str(raw or ""))
            if normalized and normalized not in out:
                out.append(normalized)
        for hint in lexical_hints:
            token = re.sub(r"[^A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]", "", hint)
            normalized_hint = fold_text(cls.normalize_entity_surface(token))
            if (
                normalized_hint
                and normalized_hint not in cls.ENTITY_TOKEN_STOPWORDS
                and normalized_hint not in cls.ENTITY_HINT_STOPWORDS
                and normalized_hint != fold_text(token)
                and normalized_hint not in out
            ):
                out.append(normalized_hint)
        return out

    @classmethod
    def text_matches_strong_entity(cls, text: str, strong_entities: list[str]) -> bool:
        if not strong_entities:
            return True
        hay_tokens = set(re.findall(r"[a-z0-9áéíóöőúüű]{2,}", fold_text(text)))
        if not hay_tokens:
            return False
        for entity in strong_entities:
            entity_tokens = [
                token
                for token in re.findall(r"[a-z0-9áéíóöőúüű]{2,}", fold_text(entity))
                if token and token not in cls.ENTITY_TOKEN_STOPWORDS
            ]
            if entity_tokens and all(cls._token_matches(token, hay_tokens) for token in entity_tokens):
                return True
        return False

    @classmethod
    def _append_explicit_pairs(cls, out: list[str], text: str) -> None:
        pairs = re.findall(r"\b([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\s+([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\b", text)
        for left, right in pairs:
            pair = cls._normalized_pair(left, right)
            if pair and pair.lower() not in {"milyen programot", "utolso kerdes", "utolsó kérdés"}:
                out.append(pair)

    @classmethod
    def _append_capitalized_sequences(cls, out: list[str], text: str) -> None:
        for match in cls.CAP_SEQ_RE.findall(text or ""):
            tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", " ".join(str(match).split()))
            while tokens and cls._token_is_stopword(tokens[0]):
                tokens.pop(0)
            value = " ".join(tokens)
            if value and value not in cls.ENTITY_STOPWORDS:
                out.append(value)

    @classmethod
    def _append_lowercase_pairs(cls, out: list[str], text: str) -> None:
        lowered = re.findall(r"\b[a-z0-9áéíóöőúüű]{2,}\b", text.lower())
        for idx in range(len(lowered) - 1):
            pair = cls._normalized_pair(lowered[idx], lowered[idx + 1])
            if pair and pair not in {"milyen programot", "programot keszitett", "programot készített"}:
                out.append(pair)

    @classmethod
    def _normalized_pair(cls, left: str, right: str) -> str:
        left_normalized = cls.normalize_entity_surface(left)
        right_normalized = cls.normalize_entity_surface(right)
        if cls._token_is_stopword(left) or cls._token_is_stopword(right):
            return ""
        pair = f"{left_normalized or left} {right_normalized or right}".strip()
        return pair if len(pair) >= 5 else ""

    @classmethod
    def _token_is_stopword(cls, token: str) -> bool:
        return fold_text(token) in cls.ENTITY_TOKEN_STOPWORDS or fold_text(cls.normalize_entity_surface(token)) in cls.ENTITY_TOKEN_STOPWORDS

    @classmethod
    def _strong_candidate_from_raw(cls, raw: str) -> str:
        text = " ".join(raw.strip().split())
        raw_tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", text)
        has_capitalized = any(token[:1].isupper() for token in raw_tokens)
        tokens = [fold_text(cls.normalize_entity_surface(token) or token) for token in raw_tokens]
        tokens = [token for token in tokens if token and token not in cls.ENTITY_TOKEN_STOPWORDS]
        if not tokens:
            return ""
        if len(tokens) == 1 and not has_capitalized and tokens[0] in cls.ENTITY_HINT_STOPWORDS:
            return ""
        if not has_capitalized and any(token in cls.ENTITY_DESCRIPTOR_TERMS for token in tokens):
            return ""
        return " ".join(tokens)

    @staticmethod
    def _token_matches(token: str, hay_tokens: set[str]) -> bool:
        return token in hay_tokens or any(QueryEntityExtractor._one_edit_or_less(token, hay_token) for hay_token in hay_tokens)

    @staticmethod
    def _one_edit_or_less(left: str, right: str) -> bool:
        if left == right:
            return True
        if not left or not right or abs(len(left) - len(right)) > 1:
            return False
        if len(left) == len(right):
            return sum(1 for idx in range(len(left)) if left[idx] != right[idx]) <= 1
        if len(left) > len(right):
            left, right = right, left
        i = j = 0
        used_skip = False
        while i < len(left) and j < len(right):
            if left[i] == right[j]:
                i += 1
                j += 1
            elif used_skip:
                return False
            else:
                used_skip = True
                j += 1
        return True


__all__ = ["QueryEntityExtractor"]
