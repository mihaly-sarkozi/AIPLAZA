# backend/apps/knowledge/service/semantic_block_selection.py
# Feladat: A KnowledgeFacade semantic block és retrieval chunk kiválasztási helper logikáját tartalmazza. Query tokenizálás, semantic block scoring, context összeállítás, vector-hit payload átalakítás és chunk sorrendezés kerül ide a facade-ból. Program-specifikus retrieval segédréteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from apps.knowledge.service.language_rules import fold_text


def semantic_block_search_text(block: dict[str, Any]) -> str:
    parts = [
        block.get("summary"),
        block.get("primary_subject"),
        block.get("subject_key"),
        block.get("primary_space"),
        block.get("primary_time"),
        block.get("text"),
        " ".join(str(item or "") for item in block.get("predicates") or []),
        " ".join(str(item or "") for item in block.get("space_values") or []),
        " ".join(str(item or "") for item in block.get("time_values") or []),
    ]
    return fold_text(" ".join(str(part or "") for part in parts))


def query_terms_for_blocks(query_profile: dict[str, Any] | None, query: str | None) -> set[str]:
    values: list[str] = [str(query or "")]
    profile = dict(query_profile or {})
    for key in ("query", "subject", "object", "expected_answer_type", "temporal_scope", "intent"):
        values.append(str(profile.get(key) or ""))
    for key in ("detected_entities", "keywords", "entity_keys", "space_values", "time_values"):
        raw = profile.get(key)
        if isinstance(raw, list):
            values.extend(str(item or "") for item in raw)
    terms: set[str] = set()
    stopwords = {"hogy", "mert", "amikor", "mikor", "mit", "milyen", "csinal", "csinál", "az", "egy", "the", "and"}
    for value in values:
        for token in fold_text(str(value or "")).replace("_", " ").split():
            token = token.strip(".,:;!?()[]{}\"'")
            if len(token) >= 2 and token not in stopwords:
                terms.add(token)
    return terms


def query_phrase_for_blocks(query: str | None) -> str:
    stopwords = {"a", "az", "egy", "mit", "miket", "milyen", "hogyan", "hogy", "csinal", "csinál", "rendszer?"}
    tokens: list[str] = []
    for token in fold_text(str(query or "")).replace("_", " ").split():
        cleaned = token.strip(".,:;!?()[]{}\"'")
        if cleaned and cleaned not in stopwords:
            tokens.append(cleaned)
    return " ".join(tokens)


def is_broad_function_query(query: str | None, query_profile: dict[str, Any] | None) -> bool:
    text = fold_text(str(query or ""))
    profile = dict(query_profile or {})
    expected = fold_text(str(profile.get("expected_answer_type") or ""))
    return "mit csinal" in text or "mire valo" in text or expected in {"object", "summary"}


def select_semantic_blocks_for_query(
    *,
    semantic_blocks: list[dict[str, Any]],
    matched_claims: list[dict[str, Any]],
    matched_chunks: list[dict[str, Any]],
    query_profile: dict[str, Any] | None = None,
    query: str | None = None,
    max_blocks: int = 4,
) -> list[dict[str, Any]]:
    claim_ids = {
        str(claim.get("claim_id") or "").strip()
        for claim in matched_claims
        if str(claim.get("claim_id") or "").strip()
    }
    profile_source_ids = {
        str(source_id or "").strip()
        for chunk in matched_chunks
        for source_id in (chunk.get("source_ids") or [])
        if str(source_id or "").strip()
    }
    query_terms = query_terms_for_blocks(query_profile, query)
    query_phrase = query_phrase_for_blocks(query)
    broad_function_query = is_broad_function_query(query, query_profile)
    scored: list[tuple[float, dict[str, Any]]] = []
    for block in semantic_blocks:
        block_status = str(block.get("block_status") or (block.get("metadata") or {}).get("block_status") or "draft").lower()
        if block_status in {"rejected", "withdrawn"}:
            continue
        score = 0.0
        block_claim_ids = {str(item or "").strip() for item in block.get("claim_ids") or [] if str(item or "").strip()}
        if claim_ids and block_claim_ids.intersection(claim_ids):
            score += 3.0
        source_id = str(block.get("source_id") or "").strip()
        if source_id and source_id in profile_source_ids:
            score += 0.25
        search_text = semantic_block_search_text(block)
        sentence_count = int((block.get("metadata") or {}).get("sentence_count") or len(block.get("sentence_ids") or []) or 0)
        exact_phrase_match = bool(query_phrase and len(query_phrase) >= 4 and query_phrase in search_text)
        if exact_phrase_match:
            score += 4.0
        if query_terms:
            matched_terms = {term for term in query_terms if term in search_text}
            coverage = len(matched_terms) / max(1, len(query_terms))
            score += min(4.0, len(matched_terms) * 0.8)
            if coverage >= 0.75:
                score += 1.0
        else:
            matched_terms = set()
        if broad_function_query and exact_phrase_match and sentence_count >= 3:
            score += 4.0
        elif broad_function_query and sentence_count >= 3 and query_terms and len(matched_terms) >= 2:
            score += 2.0
        if broad_function_query and sentence_count <= 1 and not exact_phrase_match:
            score -= 0.5
        if score > 0:
            retrieval_weight = float(block.get("retrieval_weight") or (block.get("metadata") or {}).get("retrieval_weight") or 1.0)
            quality_adjusted_score = score * max(0.0, retrieval_weight)
            enriched = dict(block)
            enriched["match_score"] = round(quality_adjusted_score, 4)
            enriched["match_reason"] = {
                "claim_overlap": bool(claim_ids and block_claim_ids.intersection(claim_ids)),
                "source_overlap": bool(source_id and source_id in profile_source_ids),
                "exact_query_phrase": exact_phrase_match,
                "broad_function_query": broad_function_query,
                "sentence_count": sentence_count,
                "query_terms": sorted(matched_terms)[:12],
                "base_score": round(score, 4),
                "retrieval_weight": round(retrieval_weight, 4),
                "block_status": block_status,
                "source_reliability": block.get("source_reliability") or (block.get("metadata") or {}).get("source_reliability"),
                "conflict_count": block.get("conflict_count") or (block.get("metadata") or {}).get("conflict_count") or 0,
            }
            scored.append((quality_adjusted_score, enriched))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _score, block in sorted(scored, key=lambda item: (-item[0], int(item[1].get("order_start") or 0))):
        block_id = str(block.get("id") or "")
        if block_id in seen:
            continue
        seen.add(block_id)
        deduped.append(block)
        if len(deduped) >= max_blocks:
            break
    return deduped


def semantic_blocks_context(blocks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    total = 0
    for index, block in enumerate(blocks, start=1):
        text = str(block.get("text") or "").strip()
        if not text:
            continue
        heading = str(block.get("summary") or block.get("primary_subject") or f"Semantic block {index}").strip()
        subject = str(block.get("primary_subject") or "-").strip() or "-"
        space = str(block.get("primary_space") or ", ".join(block.get("space_values") or []) or "-").strip() or "-"
        time = str(block.get("primary_time") or ", ".join(block.get("time_values") or []) or "-").strip() or "-"
        source_id = str(block.get("source_id") or "-").strip() or "-"
        block_id = str(block.get("id") or "-").strip() or "-"
        part = (
            f"[Tudásblokk {index}: {heading}]\n"
            f"block_id={block_id}; source_id={source_id}; alany={subject}; hely={space}; idő={time}\n"
            f"{text}"
        )
        if total + len(part) > max_chars:
            break
        parts.append(part)
        total += len(part)
    return "\n\n".join(parts)


def filter_relevant_semantic_blocks(
    blocks: list[dict[str, Any]],
    *,
    max_blocks: int = 4,
    score_floor: float = 0.25,
    relative_floor_ratio: float = 0.8,
) -> list[dict[str, Any]]:
    if not blocks:
        return []
    ordered = sorted(
        blocks,
        key=lambda item: float(item.get("match_score") or 0.0),
        reverse=True,
    )
    top_score = float(ordered[0].get("match_score") or 0.0)
    dynamic_floor = max(score_floor, top_score * relative_floor_ratio)
    selected: list[dict[str, Any]] = []
    for block in ordered:
        score = float(block.get("match_score") or 0.0)
        if score < dynamic_floor and selected:
            continue
        selected.append(block)
        if len(selected) >= max_blocks:
            break
    return selected[:max_blocks]


def retrieval_chunks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for hit in hits:
        payload = dict(hit.get("payload") or {})
        if payload.get("point_type") != "retrieval_chunk":
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        profile_id = str(payload.get("profile_id") or metadata.get("profile_id") or "").strip()
        if not profile_id:
            continue
        chunks.append(
            {
                "retrieval_chunk_id": metadata.get("retrieval_chunk_id") or f"retrieval_chunk:{profile_id}",
                "profile_id": profile_id,
                "entity_name": payload.get("entity_name"),
                "entity_type": payload.get("entity_type"),
                "canonical_key": payload.get("canonical_key") or metadata.get("canonical_key"),
                "retrieval_chunk_text": payload.get("text") or metadata.get("retrieval_chunk_text"),
                "structured_facts": metadata.get("structured_facts") or {},
                "evidence_ids": list(metadata.get("evidence_ids") or []),
                "source_ids": list(metadata.get("source_ids") or []),
                "conflicting": bool(metadata.get("conflicting")),
                "temporal_context_included": bool(metadata.get("temporal_context_included")),
                "vector_score": hit.get("fusion_score") or hit.get("score"),
            }
        )
    return chunks


def semantic_blocks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        payload = dict(hit.get("payload") or {})
        if payload.get("point_type") != "semantic_block":
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        block_id = str(payload.get("block_id") or metadata.get("block_id") or "").strip()
        if not block_id or block_id in seen:
            continue
        seen.add(block_id)
        block = {
            "id": block_id,
            "corpus_uuid": metadata.get("corpus_uuid"),
            "source_id": payload.get("source_id") or metadata.get("source_id"),
            "document_id": payload.get("document_id") or metadata.get("document_id"),
            "paragraph_ids": list(metadata.get("paragraph_ids") or []),
            "sentence_ids": list(payload.get("sentence_ids") or metadata.get("sentence_ids") or []),
            "claim_ids": list(payload.get("claim_ids") or metadata.get("claim_ids") or []),
            "order_start": metadata.get("order_start") or 0,
            "order_end": metadata.get("order_end") or 0,
            "primary_subject": payload.get("subject") or metadata.get("primary_subject") or "",
            "subject_key": payload.get("subject_key") or metadata.get("subject_key") or "",
            "primary_space": payload.get("space") or metadata.get("primary_space") or "",
            "space_key": payload.get("space_key") or metadata.get("space_key") or "",
            "primary_time": payload.get("time") or metadata.get("primary_time") or "",
            "time_key": payload.get("time_key") or metadata.get("time_key") or "",
            "block_type": metadata.get("block_type") or "semantic_unit",
            "text": metadata.get("text") or payload.get("raw_block_text") or payload.get("text") or "",
            "summary": metadata.get("summary") or "",
            "predicates": list(metadata.get("predicates") or []),
            "entity_keys": list(payload.get("entity_keys") or metadata.get("entity_keys") or []),
            "space_modes": list(payload.get("space_modes") or metadata.get("space_modes") or []),
            "space_values": list(metadata.get("space_values") or []),
            "time_modes": list(payload.get("time_modes") or metadata.get("time_modes") or []),
            "time_values": list(metadata.get("time_values") or []),
            "confidence": metadata.get("confidence") or 0.0,
            "block_status": payload.get("block_status") or metadata.get("block_status") or "draft",
            "source_reliability": payload.get("source_reliability") or metadata.get("source_reliability") or 0.0,
            "retrieval_weight": payload.get("retrieval_weight") or metadata.get("retrieval_weight") or 1.0,
            "conflict_count": payload.get("conflict_count") or metadata.get("conflict_count") or 0,
            "conflicts": list(metadata.get("conflicts") or []),
            "builder_version": metadata.get("builder_version") or "",
            "metadata": dict(metadata.get("metadata") or {}),
            "match_score": round(float(hit.get("fusion_score") or hit.get("score") or 0.0), 4),
            "match_reason": {
                "vector_hit": True,
                "semantic_score": hit.get("semantic_score"),
                "lexical_score": hit.get("lexical_score"),
                "fusion_score": hit.get("fusion_score"),
                "quality_score": payload.get("quality_score_explanation") or {},
                "point_type": "semantic_block",
            },
        }
        blocks.append(block)
    return blocks


def order_chunks_by_vector_hits(retrieval_chunks: list[dict[str, Any]], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vector_profile_ids = [
        str((hit.get("payload") or {}).get("profile_id") or "").strip()
        for hit in hits
        if (hit.get("payload") or {}).get("point_type") == "retrieval_chunk"
    ]
    vector_profile_ids = [item for item in vector_profile_ids if item]
    if not vector_profile_ids:
        return retrieval_chunks
    rank = {profile_id: index for index, profile_id in enumerate(vector_profile_ids)}
    matched = [chunk for chunk in retrieval_chunks if str(chunk.get("profile_id") or "") in rank]
    if not matched:
        return retrieval_chunks_from_vector_hits(hits) or retrieval_chunks
    remainder = [chunk for chunk in retrieval_chunks if str(chunk.get("profile_id") or "") not in rank]
    return sorted(matched, key=lambda chunk: rank.get(str(chunk.get("profile_id") or ""), 9999)) + remainder


__all__ = [
    "filter_relevant_semantic_blocks",
    "is_broad_function_query",
    "order_chunks_by_vector_hits",
    "query_phrase_for_blocks",
    "query_terms_for_blocks",
    "retrieval_chunks_from_vector_hits",
    "select_semantic_blocks_for_query",
    "semantic_block_search_text",
    "semantic_blocks_context",
    "semantic_blocks_from_vector_hits",
]
