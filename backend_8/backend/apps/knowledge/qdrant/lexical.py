# backend/apps/knowledge/qdrant/lexical.py
# Feladat: Qdrant retrieval lexical scoring és point-id normalizálási helper függvényeket tartalmaz. Tokenizálást, phrase/rare-term scoringot, payload szöveg normalizálást és determinisztikus Qdrant UUID képzést választ le a wrapperről. Program-specifikus knowledge retrieval scoring utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
from typing import Any
import uuid as uuid_lib


def normalize_point_id(raw_id: Any, *, point_type: str | None = None) -> str:
    text = str(raw_id or "").strip()
    if not text:
        return str(uuid_lib.uuid4())
    try:
        return str(uuid_lib.UUID(text))
    except Exception:
        namespace_text = f"{point_type or 'point'}:{text}"
        return str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, namespace_text))


def normalize_lexical_text(text: str) -> str:
    lowered = str(text or "").lower()
    cleaned = re.sub(r"[^\wáéíóöőúüű\s-]", " ", lowered, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def expanded_lexical_tokens(text: str) -> list[str]:
    normalized = normalize_lexical_text(text)
    if not normalized:
        return []
    base_tokens = re.findall(r"[a-z0-9áéíóöőúüű_-]+", normalized)
    expanded: list[str] = []
    seen: set[str] = set()
    for token in base_tokens:
        candidates = [token]
        if "-" in token or "_" in token:
            candidates.extend(part for part in re.split(r"[-_]+", token) if part)
        for candidate in candidates:
            item = str(candidate or "").strip()
            if len(item) < 2 or item in seen:
                continue
            seen.add(item)
            expanded.append(item)
    return expanded


def lexical_tokens(text: str) -> list[str]:
    return expanded_lexical_tokens(text)


def token_shape_boost(token: str) -> float:
    if any(ch.isdigit() for ch in token) or "-" in token or "_" in token:
        return 1.0
    if len(token) >= 10:
        return 0.92
    if len(token) >= 8:
        return 0.78
    return 0.45


def payload_lexical_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("text", "canonical_text", "canonical_name", "predicate"):
        value = str(payload.get(key) or "").strip()
        if value:
            parts.append(value)
    for key in ("aliases", "place_keys", "place_hierarchy_keys"):
        for value in (payload.get(key) or []):
            item = str(value or "").strip()
            if item:
                parts.append(item)
    return normalize_lexical_text(" ".join(parts))


def near_exact_phrase_score(query_text: str, payload_text: str) -> float:
    q = normalize_lexical_text(query_text)
    p = normalize_lexical_text(payload_text)
    if not q or not p:
        return 0.0
    if q == p:
        return 1.0
    if q in p or p in q:
        shorter = min(len(q), len(p))
        longer = max(len(q), len(p))
        return max(0.0, min(0.96, shorter / max(1, longer)))
    q_compact = q.replace(" ", "")
    p_compact = p.replace(" ", "")
    if q_compact and p_compact and (q_compact in p_compact or p_compact in q_compact):
        shorter = min(len(q_compact), len(p_compact))
        longer = max(len(q_compact), len(p_compact))
        return max(0.0, min(0.92, shorter / max(1, longer)))
    return 0.0


def weighted_overlap_score(query_tokens: list[str], text_tokens: list[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    text_token_set = set(text_tokens)
    total_weight = 0.0
    matched_weight = 0.0
    for token in query_tokens:
        weight = token_shape_boost(token)
        total_weight += weight
        if token in text_token_set:
            matched_weight += weight
    if total_weight <= 0.0:
        return 0.0
    return max(0.0, min(1.0, matched_weight / total_weight))


def rare_term_score(rare_terms: list[str], payload_text: str, payload_tokens: list[str]) -> float:
    rare_tokens = lexical_tokens(" ".join(rare_terms or []))
    if not rare_tokens:
        return 0.0
    text_norm = normalize_lexical_text(payload_text)
    payload_token_set = set(payload_tokens)
    total = 0.0
    matched = 0.0
    for token in rare_tokens:
        weight = 0.7 + (0.3 * token_shape_boost(token))
        total += weight
        if token in payload_token_set:
            matched += weight
        elif token in text_norm:
            matched += weight * 0.82
    if total <= 0.0:
        return 0.0
    return max(0.0, min(1.0, matched / total))


__all__ = [
    "expanded_lexical_tokens",
    "lexical_tokens",
    "near_exact_phrase_score",
    "normalize_lexical_text",
    "normalize_point_id",
    "payload_lexical_text",
    "rare_term_score",
    "token_shape_boost",
    "weighted_overlap_score",
]
