# backend/apps/chat/service/chat_query_enrichment_service.py
# Owns chat query enrichment: entities, places, time hints, intent and follow-up detection.

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from apps.chat.service.chat_text_utils import dedupe_keep_order, fold_lexicon_token, fold_text
from core.kernel.runtime.clock import utc_now_naive
from shared.text.language_lexicon import SUPPORTED_LEXICON_LANGUAGES, get_lexicon_terms, get_month_number


def _fold_lexicon_token(value: str) -> str:
    return fold_lexicon_token(value)


class ChatQueryEnrichmentService:
    _ENTITY_TOKEN_STOPWORDS = {
        _fold_lexicon_token(token)
        for language_code in SUPPORTED_LEXICON_LANGUAGES
        for token in get_lexicon_terms(language_code, "entity_stopwords")
    }
    _ENTITY_HINT_STOPWORDS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "entity_hint_stopwords")
    }
    _ENTITY_DESCRIPTOR_TERMS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "descriptor_terms")
    }
    _ENTITY_SUFFIXES = get_lexicon_terms("hu", "entity_suffixes", include_fallback=False)
    _YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
    _DATE_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
    _YEAR_MONTH_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])\b")
    _CAP_SEQ_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)*\b")
    _WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]{3,}")
    _MONTHS = {
        month_name: get_month_number("hu", month_name)
        for month_name in get_lexicon_terms("hu", "time_months", include_fallback=False)
        if get_month_number("hu", month_name) is not None
    }
    _ENTITY_STOPWORDS = {
        token.capitalize()
        for token in get_lexicon_terms("hu", "question_words", include_fallback=False)
    } | {"Mutasd", "Mondd", "Keresd", "Van", "Volt", "Lesz", "A", "Az", "És", "Vagy"}
    _PLACE_SUFFIXES = get_lexicon_terms("hu", "place_suffixes", include_fallback=False)
    _QUESTION_STOPWORDS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "question_stopwords")
    }

    def __init__(self) -> None:
        self._recent_query_focus_by_user: dict[int, dict[str, Any]] = {}

    @staticmethod
    def _utcnow_naive() -> datetime:
        return utc_now_naive()

    @staticmethod
    def _dedupe_keep_order(values: list[str]) -> list[str]:
        return dedupe_keep_order(values)

    @staticmethod
    def _fold_text(value: str | None) -> str:
        return fold_text(value)

    @classmethod
    def normalize_place_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        if cls._fold_text(raw) in cls._QUESTION_STOPWORDS:
            return raw
        lower = raw.lower()
        for suffix in sorted(cls._PLACE_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                return raw[: len(raw) - len(suffix)]
        return raw

    @classmethod
    def normalize_entity_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        lower = raw.lower()
        for suffix in sorted(cls._ENTITY_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                candidate = raw[: len(raw) - len(suffix)]
                if candidate and candidate[:1].isalpha():
                    return candidate
        return raw

    @classmethod
    def extract_entity_candidates(cls, question: str) -> list[str]:
        out: list[str] = []
        text = str(question or "")
        explicit_pairs = re.findall(
            r"\b([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\s+([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\b",
            text,
        )
        for left, right in explicit_pairs:
            left_normalized = cls.normalize_entity_surface(left)
            right_normalized = cls.normalize_entity_surface(right)
            left_folded_raw = cls._fold_text(left)
            right_folded_raw = cls._fold_text(right)
            left_folded_normalized = cls._fold_text(left_normalized or left)
            right_folded_normalized = cls._fold_text(right_normalized or right)
            if (
                left_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or left_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
            ):
                continue
            pair = f"{left_normalized or left} {right_normalized or right}".strip()
            if len(pair) >= 5 and pair.lower() not in {"milyen programot", "utolso kerdes", "utolsó kérdés"}:
                out.append(pair)
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            value = " ".join(str(match).split())
            if not value:
                continue
            tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", value)
            while tokens:
                first_raw_folded = cls._fold_text(tokens[0])
                first_normalized_folded = cls._fold_text(cls.normalize_entity_surface(tokens[0]) or tokens[0])
                if first_raw_folded in cls._ENTITY_TOKEN_STOPWORDS or first_normalized_folded in cls._ENTITY_TOKEN_STOPWORDS:
                    tokens.pop(0)
                else:
                    break
            if not tokens:
                continue
            value = " ".join(tokens)
            if value in cls._ENTITY_STOPWORDS:
                continue
            out.append(value)
        lowered = re.findall(r"\b[a-z0-9áéíóöőúüű]{2,}\b", text.lower())
        for idx in range(len(lowered) - 1):
            left_normalized = cls.normalize_entity_surface(lowered[idx])
            right_normalized = cls.normalize_entity_surface(lowered[idx + 1])
            left_folded_raw = cls._fold_text(lowered[idx])
            right_folded_raw = cls._fold_text(lowered[idx + 1])
            left_folded_normalized = cls._fold_text(left_normalized or lowered[idx])
            right_folded_normalized = cls._fold_text(right_normalized or lowered[idx + 1])
            if (
                left_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or left_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
            ):
                continue
            pair = f"{left_normalized or lowered[idx]} {right_normalized or lowered[idx + 1]}".strip()
            if pair in {"milyen programot", "programot keszitett", "programot készített"}:
                continue
            if len(pair) >= 5:
                out.append(pair)
        return cls._dedupe_keep_order(out)

    @classmethod
    def strong_entity_candidates(cls, query_profile: dict[str, Any]) -> list[str]:
        out: list[str] = []
        lexical_hints = [str(item or "").strip() for item in (query_profile.get("lexical_focus_terms") or [])]
        for raw in query_profile.get("entity_candidates") or []:
            text = " ".join(str(raw or "").strip().split())
            if not text:
                continue
            raw_tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", text)
            if not raw_tokens:
                continue
            has_capitalized_token = any(token[:1].isupper() for token in raw_tokens)
            tokens: list[str] = []
            for token in raw_tokens:
                normalized = cls.normalize_entity_surface(token)
                folded = cls._fold_text(normalized or token)
                if not folded or folded in cls._ENTITY_TOKEN_STOPWORDS:
                    continue
                tokens.append(folded)
            if not tokens:
                continue
            if len(tokens) == 1 and not has_capitalized_token:
                single = tokens[0]
                if single in cls._ENTITY_HINT_STOPWORDS or single in cls._ENTITY_DESCRIPTOR_TERMS:
                    continue
            if not has_capitalized_token and any(token in cls._ENTITY_DESCRIPTOR_TERMS for token in tokens):
                continue
            normalized = " ".join(tokens)
            if normalized and normalized not in out:
                out.append(normalized)
        for hint in lexical_hints:
            token = re.sub(r"[^A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]", "", hint)
            if not token:
                continue
            folded_token = cls._fold_text(token)
            if not folded_token or folded_token in cls._ENTITY_TOKEN_STOPWORDS:
                continue
            normalized_hint = cls._fold_text(cls.normalize_entity_surface(token))
            if not normalized_hint or normalized_hint in cls._ENTITY_TOKEN_STOPWORDS:
                continue
            if normalized_hint in cls._ENTITY_HINT_STOPWORDS:
                continue
            if normalized_hint == folded_token:
                continue
            if normalized_hint not in out:
                out.append(normalized_hint)
        return out

    @classmethod
    def text_matches_strong_entity(cls, text: str, strong_entities: list[str]) -> bool:
        if not strong_entities:
            return True
        haystack = cls._fold_text(text)
        if not haystack:
            return False
        hay_tokens = {
            token
            for token in re.findall(r"[a-z0-9áéíóöőúüű]{2,}", haystack)
            if token
        }
        if not hay_tokens:
            return False

        def one_edit_or_less(left: str, right: str) -> bool:
            if left == right:
                return True
            if not left or not right:
                return False
            len_left, len_right = len(left), len(right)
            if abs(len_left - len_right) > 1:
                return False
            if len_left == len_right:
                mismatch = sum(1 for idx in range(len_left) if left[idx] != right[idx])
                return mismatch <= 1
            if len_left > len_right:
                left, right = right, left
                len_left, len_right = len_right, len_left
            i = 0
            j = 0
            used_skip = False
            while i < len_left and j < len_right:
                if left[i] == right[j]:
                    i += 1
                    j += 1
                    continue
                if used_skip:
                    return False
                used_skip = True
                j += 1
            return True

        for entity in strong_entities:
            entity_tokens = [
                token
                for token in re.findall(r"[a-z0-9áéíóöőúüű]{2,}", cls._fold_text(entity))
                if token and token not in cls._ENTITY_TOKEN_STOPWORDS
            ]
            if not entity_tokens:
                continue
            if len(entity_tokens) == 1 and (
                entity_tokens[0] in hay_tokens
                or any(one_edit_or_less(entity_tokens[0], hay_token) for hay_token in hay_tokens)
            ):
                return True
            if len(entity_tokens) > 1 and all(
                token in hay_tokens or any(one_edit_or_less(token, hay_token) for hay_token in hay_tokens)
                for token in entity_tokens
            ):
                return True
        return False

    @classmethod
    def extract_place_candidates(cls, question: str) -> list[str]:
        words = re.findall(r"\b[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+\b", question or "")
        out: list[str] = []
        for word in words:
            normalized = cls.normalize_place_surface(word)
            if normalized != word and normalized[:1].isupper():
                if cls._fold_text(word) in cls._QUESTION_STOPWORDS:
                    continue
                if cls._fold_text(normalized) in cls._QUESTION_STOPWORDS:
                    continue
                out.append(normalized)
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            low = f" {(question or '').lower()} "
            value = " ".join(str(match).split())
            if not value:
                continue
            probe = value.lower()
            if any(
                token in low
                for token in (
                    f" {probe.lower()} ban ", f" {probe.lower()} ben ", f" {probe.lower()} on ",
                    f" {probe.lower()} en ", f" {probe.lower()} ön ", f" {probe.lower()} területén ",
                    f" {probe.lower()} városban ", f" {probe.lower()} megyében ",
                )
            ):
                out.append(value)
        return cls._dedupe_keep_order(out)

    @classmethod
    def extract_time_hints(cls, question: str) -> tuple[list[str], dict[str, datetime | None]]:
        text = str(question or "")
        low = text.lower()
        now = cls._utcnow_naive()
        candidates: list[str] = []
        window: dict[str, datetime | None] = {"from": None, "to": None}
        for year, month, day in cls._DATE_RE.findall(text):
            candidates.append(f"{year}-{month}-{day}")
            dt = datetime(int(year), int(month), int(day), 0, 0, 0)
            window["from"] = dt
            window["to"] = dt.replace(hour=23, minute=59, second=59)
            return cls._dedupe_keep_order(candidates), window
        for year, month in cls._YEAR_MONTH_RE.findall(text):
            candidates.append(f"{year}-{month}")
            start = datetime(int(year), int(month), 1, 0, 0, 0)
            if int(month) == 12:
                end = datetime(int(year), 12, 31, 23, 59, 59)
            else:
                end = datetime(int(year), int(month) + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            window["from"] = start
            window["to"] = end
            return cls._dedupe_keep_order(candidates), window
        years = cls._YEAR_RE.findall(text)
        if years:
            year = int(years[0])
            candidates.extend(years)
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
            return cls._dedupe_keep_order(candidates), window
        for month_name, month_num in cls._MONTHS.items():
            if month_name in low:
                candidates.append(month_name)
                year = now.year
                year_match = cls._YEAR_RE.search(text)
                if year_match:
                    year = int(year_match.group(1))
                start = datetime(year, month_num, 1, 0, 0, 0)
                if month_num == 12:
                    end = datetime(year, 12, 31, 23, 59, 59)
                else:
                    end = datetime(year, month_num + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                window["from"] = start
                window["to"] = end
                return cls._dedupe_keep_order(candidates), window
        if "tavaly" in low:
            year = now.year - 1
            candidates.append("tavaly")
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
        elif "idén" in low:
            candidates.append("idén")
            window["from"] = datetime(now.year, 1, 1, 0, 0, 0)
            window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
        elif "most" in low or "jelenleg" in low:
            candidates.append("most")
            window["from"] = datetime(now.year, now.month, 1, 0, 0, 0)
            if now.month == 12:
                window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
            else:
                window["to"] = datetime(now.year, now.month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
        return cls._dedupe_keep_order(candidates), window

    @classmethod
    def derive_intent(cls, question: str, parsed: dict[str, Any]) -> str:
        low = str(question or "").lower()
        if any(x in low for x in ("időrend", "timeline", "mikor", "meddig", "mettől", "előtte", "utána")):
            return "timeline"
        if any(x in low for x in ("kapcsolat", "viszony", "kapcsolódik", "kapcsolódnak", "köze van")):
            return "relation"
        if any(x in low for x in ("milyen", "mennyi", "mekkora", "státusz", "állapot", "attribútum")):
            return "attribute"
        if any(x in low for x in ("mit csinál", "mit csinált", "mi történt", "ki dolgozik", "ki vezet")):
            return "activity"
        entities = parsed.get("entity_candidates") or []
        predicates = parsed.get("predicate_candidates") or []
        if predicates and entities:
            return "activity"
        return str(parsed.get("intent") or "summary")

    @classmethod
    def looks_broad_enumeration_request(cls, question: str) -> bool:
        q = str(question or "").strip().lower()
        if not q:
            return False
        signals = (
            "összes tudás",
            "minden tudás",
            "listázd az összes",
            "listázz mindent",
            "minden adat",
            "teljes tudásbázis",
            "all knowledge",
            "list everything",
            "dump all",
            "show all records",
            "export all",
        )
        return any(token in q for token in signals)

    @classmethod
    def build_hint_terms(cls, question: str, parsed: dict[str, Any]) -> list[str]:
        low = str(question or "").lower()
        tokens = [token for token in cls._WORD_RE.findall(low) if token not in cls._QUESTION_STOPWORDS]
        blocked = {
            str(x).lower()
            for key in ("entity_candidates", "place_candidates", "time_candidates")
            for x in (parsed.get(key) or [])
        }
        out = [
            token for token in tokens
            if token not in blocked and len(token) >= 4
        ]
        return cls._dedupe_keep_order(out[:8])

    @classmethod
    def enrich(cls, question: str, parsed: dict[str, Any]) -> dict[str, Any]:
        parsed = dict(parsed or {})
        parsed.setdefault("raw_query", question)
        parsed["entity_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("entity_candidates") or []) + cls.extract_entity_candidates(question)
        )
        parsed["place_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("place_candidates") or []) + cls.extract_place_candidates(question)
        )
        time_candidates, time_window = cls.extract_time_hints(question)
        parsed["time_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("time_candidates") or []) + time_candidates
        )
        if parsed.get("query_valid_time_from") is None and time_window.get("from") is not None:
            parsed["query_valid_time_from"] = time_window["from"]
        if parsed.get("query_valid_time_to") is None and time_window.get("to") is not None:
            parsed["query_valid_time_to"] = time_window["to"]
        parsed["valid_time_window"] = parsed.get("valid_time_window") or {
            "from": parsed.get("query_valid_time_from").isoformat() if parsed.get("query_valid_time_from") else None,
            "to": parsed.get("query_valid_time_to").isoformat() if parsed.get("query_valid_time_to") else None,
        }
        parsed["time_window"] = parsed.get("time_window") or parsed["valid_time_window"]
        parsed["intent"] = cls.derive_intent(question, parsed)
        hint_terms = cls.build_hint_terms(question, parsed)
        parsed["lexical_focus_terms"] = cls._dedupe_keep_order(
            list(parsed.get("lexical_focus_terms") or [])
            + list(parsed.get("predicate_candidates") or [])
            + list(parsed.get("attribute_candidates") or [])
            + list(parsed.get("relation_candidates") or [])
            + hint_terms
        )
        parsed["entity_heavy"] = bool(parsed.get("entity_heavy")) or len(parsed["entity_candidates"]) >= 2
        parsed["predicate_heavy"] = bool(parsed.get("predicate_heavy")) or bool(parsed.get("predicate_candidates"))
        if not parsed.get("retrieval_mode") or parsed.get("retrieval_mode") == "assertion_first":
            intent = str(parsed.get("intent") or "summary")
            if intent == "timeline":
                parsed["retrieval_mode"] = "timeline_first"
            elif intent in {"relation", "attribute"} or parsed.get("entity_heavy"):
                parsed["retrieval_mode"] = "entity_first"
            else:
                parsed["retrieval_mode"] = "assertion_first"
        representation_parts = [
            str(parsed.get("raw_query") or question),
            " ".join(parsed.get("entity_candidates") or []),
            " ".join(parsed.get("place_candidates") or []),
            " ".join(parsed.get("time_candidates") or []),
            " ".join(parsed.get("predicate_candidates") or []),
            " ".join(parsed.get("relation_candidates") or []),
            " ".join(parsed.get("attribute_candidates") or []),
            " ".join(parsed.get("lexical_focus_terms") or []),
        ]
        normalized_representation = " ".join(part.strip() for part in representation_parts if str(part).strip())
        parsed["normalized_query_text"] = parsed.get("normalized_query_text") or normalized_representation
        parsed["lexical_query_text"] = parsed.get("lexical_query_text") or normalized_representation
        parsed["query_embedding_text"] = parsed.get("query_embedding_text") or normalized_representation
        parser_audit = dict(parsed.get("parser_audit") or {})
        parser_audit["chat_enrichment"] = {
            "entity_candidates": parsed.get("entity_candidates") or [],
            "time_candidates": parsed.get("time_candidates") or [],
            "place_candidates": parsed.get("place_candidates") or [],
            "intent": parsed.get("intent"),
            "retrieval_mode": parsed.get("retrieval_mode"),
            "lexical_focus_terms": parsed.get("lexical_focus_terms") or [],
            "normalized_query_text": parsed.get("normalized_query_text"),
        }
        parsed["parser_audit"] = parser_audit
        return parsed

    def is_followup(self, user_id: int | None, query_focus: dict[str, Any]) -> bool:
        if user_id is None:
            return False
        prev = self._recent_query_focus_by_user.get(int(user_id))
        now = self._utcnow_naive()
        self._recent_query_focus_by_user[int(user_id)] = {
            "at": now,
            "entity_candidates": query_focus.get("entity_candidates") or [],
            "valid_time_window": query_focus.get("valid_time_window") or query_focus.get("time_window") or {},
        }
        if not prev:
            return False
        prev_at = prev.get("at")
        if not isinstance(prev_at, datetime):
            return False
        if (now - prev_at).total_seconds() > 300:
            return False
        prev_entities = {str(x).lower() for x in (prev.get("entity_candidates") or [])}
        curr_entities = {str(x).lower() for x in (query_focus.get("entity_candidates") or [])}
        if prev_entities.intersection(curr_entities):
            return True
        prev_tw = prev.get("valid_time_window") or prev.get("time_window") or {}
        curr_tw = query_focus.get("valid_time_window") or query_focus.get("time_window") or {}
        return bool(prev_tw.get("from") and curr_tw.get("from") and prev_tw.get("from") == curr_tw.get("from"))


__all__ = ["ChatQueryEnrichmentService"]
