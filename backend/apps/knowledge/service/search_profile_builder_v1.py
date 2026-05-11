"""TechnicalMemoryChunk -> SearchProfile builder (v1).

Korlátok: nincs candidate selection, nincs similarity engine, nincs Qdrant indexelés.
Csak strukturált, lokális keresési profil készül.
"""
from __future__ import annotations

import re
from typing import Any

from apps.knowledge.domain.search_profile import SEARCH_PROFILE_BUILDER_VERSION, SearchProfile
from apps.knowledge.domain.technical_memory_chunk import TechnicalMemoryChunk
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from shared.text.language_lexicon import SUPPORTED_LEXICON_LANGUAGES, get_lexicon_terms


_MAX_SEARCH_TEXT_LENGTH = 1000
_KEYWORD_STOPWORDS: set[str] = set()
for _lang in SUPPORTED_LEXICON_LANGUAGES:
    _KEYWORD_STOPWORDS.update(token.lower() for token in get_lexicon_terms(_lang, "question_stopwords"))
    _KEYWORD_STOPWORDS.update(token.lower() for token in get_lexicon_terms(_lang, "time_relative_current"))
    _KEYWORD_STOPWORDS.update(token.lower() for token in get_lexicon_terms(_lang, "time_relative_bounded"))
    _KEYWORD_STOPWORDS.update(token.lower() for token in get_lexicon_terms(_lang, "time_relative_open"))
_KEYWORD_STOPWORDS.update({"még", "meg"})
_KEYWORD_TOKEN_RE = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüűñÑ]+", flags=re.UNICODE)
_CLAIM_GROUP_SIGNAL_KEYS = ("relation", "state", "rule", "event", "descriptor", "other")


def _token_count(value: str) -> int:
    return len([token for token in value.split() if token])


def _append_unique(values: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _append_if_not_covered(values: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if not text:
        return
    folded = text.lower()
    if any(folded in existing.lower() for existing in values):
        return
    values.append(text)


def _fact_text(fact: dict[str, Any]) -> str:
    predicate = str(fact.get("predicate") or "").strip()
    object_text = str(fact.get("object_text") or "").strip()
    if predicate.startswith("is "):
        predicate = predicate[3:].strip()
    elif predicate.startswith("was "):
        predicate = predicate[4:].strip()
    if predicate and object_text:
        return f"{predicate} {object_text}"
    return predicate or object_text


def _keywords_from_texts(texts: list[str]) -> list[str]:
    keywords: list[str] = []
    for text in texts:
        for raw in _KEYWORD_TOKEN_RE.findall(str(text or "")):
            token = raw.lower()
            if len(token) < 2 or token in _KEYWORD_STOPWORDS:
                continue
            _append_unique(keywords, token)
    return keywords[:40]


def _canonical_text(chunk: TechnicalMemoryChunk) -> str:
    parts: list[str] = []
    _append_unique(parts, chunk.entity_name)
    _append_unique(parts, chunk.entity_type)
    for fact in chunk.facts:
        _append_unique(parts, _fact_text(fact))
    for value in chunk.time_profile.get("time_values") or []:
        should_append = True
        for fact in chunk.facts:
            object_text = str(fact.get("object_text") or "").strip()
            fact_text = _fact_text(fact)
            if not object_text:
                if (
                    str(fact.get("claim_group") or "") != "event"
                    and str(value or "").strip().lower() in fact_text.lower()
                ):
                    should_append = False
                    break
                continue
            if object_text == str(value or "").strip():
                should_append = False
                break
            if (
                str(fact.get("claim_group") or "") != "event"
                and str(value or "").strip().lower() in object_text.lower()
            ):
                should_append = False
                break
        if should_append:
            _append_unique(parts, value)
    for value in chunk.space_profile.get("space_values") or []:
        _append_unique(parts, value)
        if parts and parts[-1] != str(value or "").strip() and str(value or "").strip() == chunk.entity_name:
            parts.append(str(value).strip())
    return " | ".join(parts)


def _search_text(chunk: TechnicalMemoryChunk, keywords: list[str]) -> str:
    parts: list[str] = []
    _append_unique(parts, chunk.entity_name)
    _append_unique(parts, chunk.entity_type)
    _append_unique(parts, chunk.summary_text)
    for fact in chunk.facts:
        _append_unique(parts, _fact_text(fact))
    for value in chunk.time_profile.get("time_values") or []:
        _append_unique(parts, value)
    for value in chunk.space_profile.get("space_values") or []:
        _append_unique(parts, value)
    for value in chunk.relation_profile.get("relation_objects") or []:
        _append_unique(parts, value)
    for keyword in keywords:
        _append_unique(parts, keyword)
    text = " | ".join(parts)
    if len(text) <= _MAX_SEARCH_TEXT_LENGTH:
        return text
    return text[:_MAX_SEARCH_TEXT_LENGTH].rsplit(" | ", 1)[0].strip() or text[:_MAX_SEARCH_TEXT_LENGTH].strip()


def _is_short_alias_candidate(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if len(text) > 40 or _token_count(text) > 3:
        return False
    if any(mark in text for mark in ".!?;:"):
        return False
    return True


def _aliases(chunk: TechnicalMemoryChunk) -> list[str]:
    aliases: list[str] = []
    _append_unique(aliases, chunk.entity_name)
    _append_unique(aliases, chunk.normalized_key)
    for ref in chunk.evidence_refs:
        if not isinstance(ref, dict):
            continue
        _append_unique(aliases, ref.get("surface_text"))
        _append_unique(aliases, ref.get("mention_text"))
        _append_unique(aliases, ref.get("normalized_text"))
    if chunk.entity_type != "person":
        for value in chunk.relation_profile.get("relation_objects") or []:
            text = str(value or "").strip()
            if _is_short_alias_candidate(text):
                _append_unique(aliases, text)
    return aliases


def _claim_group_signals(chunk: TechnicalMemoryChunk) -> dict[str, int]:
    signals = {key: 0 for key in _CLAIM_GROUP_SIGNAL_KEYS}
    for fact in chunk.facts:
        group = str(fact.get("claim_group") or "other")
        if group not in signals:
            group = "other"
        signals[group] += 1
    return signals


def _time_filters(chunk: TechnicalMemoryChunk) -> dict[str, Any]:
    profile = dict(chunk.time_profile or {})
    return {
        "dominant": profile.get("dominant_time_mode") or "unknown",
        "values": list(profile.get("time_values") or []),
        "has_current": bool(profile.get("has_current_claims")),
        "has_historical": bool(profile.get("has_historical_claims")),
    }


def _space_filters(chunk: TechnicalMemoryChunk) -> dict[str, Any]:
    profile = dict(chunk.space_profile or {})
    return {
        "dominant": profile.get("dominant_space_mode") or "unknown",
        "values": list(profile.get("space_values") or []),
        "has_bounded": bool(profile.get("has_bounded_space")),
    }


def _relation_filters(chunk: TechnicalMemoryChunk) -> dict[str, list[str]]:
    predicates: list[str] = []
    objects: list[str] = []
    for fact in chunk.facts:
        if str(fact.get("claim_group") or "") != "relation":
            continue
        _append_unique(predicates, fact.get("predicate"))
        _append_unique(objects, fact.get("object_text"))
    return {
        "predicates": predicates,
        "objects": objects,
    }


def _profile_normalized_key(chunk: TechnicalMemoryChunk) -> str:
    if str(chunk.entity_type or "") == "person":
        return chunk.normalized_key
    canonical = canonicalize_entity_key(chunk.normalized_key or chunk.entity_name)
    return canonical or chunk.normalized_key


def _profile_canonical_key(chunk: TechnicalMemoryChunk) -> str:
    if str(chunk.entity_type or "") == "person":
        return chunk.normalized_key
    return canonicalize_entity_key(chunk.normalized_key or chunk.entity_name) or chunk.normalized_key


def _evidence_refs(chunk: TechnicalMemoryChunk) -> list[dict[str, Any]]:
    claim_ids: list[str] = []
    sentence_ids: list[str] = []
    source_id = str(chunk.source_id) if chunk.source_id is not None else None
    for fact in chunk.facts:
        _append_unique(claim_ids, fact.get("claim_id"))
        _append_unique(sentence_ids, fact.get("sentence_id"))
    for ref in chunk.evidence_refs:
        if not isinstance(ref, dict):
            continue
        _append_unique(claim_ids, ref.get("claim_id"))
        _append_unique(sentence_ids, ref.get("sentence_id"))
        if source_id is None and ref.get("source_id"):
            source_id = str(ref.get("source_id"))
    return [
        {
            "claim_ids": claim_ids,
            "sentence_ids": sentence_ids,
            "source_id": source_id,
        }
    ]


class SearchProfileBuilderV1:
    version: str = SEARCH_PROFILE_BUILDER_VERSION

    def build(self, technical_memory_chunk: TechnicalMemoryChunk) -> SearchProfile:
        canonical_text = _canonical_text(technical_memory_chunk)
        keyword_source: list[str] = [
            technical_memory_chunk.entity_name,
            technical_memory_chunk.entity_type,
        ]
        for fact in technical_memory_chunk.facts:
            keyword_source.append(str(fact.get("predicate") or ""))
            keyword_source.append(str(fact.get("object_text") or ""))
        keyword_source.extend(str(value) for value in technical_memory_chunk.time_profile.get("time_values") or [])
        keyword_source.extend(str(value) for value in technical_memory_chunk.space_profile.get("space_values") or [])
        keywords = _keywords_from_texts(keyword_source)
        aliases = _aliases(technical_memory_chunk)
        return SearchProfile(
            run_id=technical_memory_chunk.run_id,
            source_id=technical_memory_chunk.source_id,
            technical_memory_chunk_id=technical_memory_chunk.technical_memory_chunk_id,
            technical_entity_id=technical_memory_chunk.technical_entity_id,
            local_entity_id=technical_memory_chunk.local_entity_id,
            entity_name=technical_memory_chunk.entity_name,
            entity_type=technical_memory_chunk.entity_type,
            normalized_key=_profile_normalized_key(technical_memory_chunk),
            canonical_key=_profile_canonical_key(technical_memory_chunk),
            canonical_text=canonical_text,
            search_text=_search_text(technical_memory_chunk, keywords),
            aliases=aliases,
            keywords=keywords,
            claim_group_signals=_claim_group_signals(technical_memory_chunk),
            time_filters=_time_filters(technical_memory_chunk),
            space_filters=_space_filters(technical_memory_chunk),
            relation_filters=_relation_filters(technical_memory_chunk),
            evidence_refs=_evidence_refs(technical_memory_chunk),
            builder_version=self.version,
        )

    def build_many(self, technical_memory_chunks: list[TechnicalMemoryChunk]) -> list[SearchProfile]:
        return [self.build(item) for item in technical_memory_chunks]


__all__ = ["SearchProfileBuilderV1"]
