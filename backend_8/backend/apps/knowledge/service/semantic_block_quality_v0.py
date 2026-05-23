from __future__ import annotations

from typing import Any

from apps.knowledge.service.language_rules import fold_text
from apps.knowledge.service.source_reliability import reliability_for_source_type


BLOCK_STATUS_APPROVED = "approved"
BLOCK_STATUS_DRAFT = "draft"
BLOCK_STATUS_DISPUTED = "disputed"
BLOCK_STATUS_REJECTED = "rejected"
BLOCK_STATUS_WITHDRAWN = "withdrawn"
BLOCK_STATUS_OUTDATED = "outdated"

_ACTIVE_STATUSES = {BLOCK_STATUS_APPROVED, BLOCK_STATUS_DRAFT, BLOCK_STATUS_DISPUTED, BLOCK_STATUS_OUTDATED}
_STATUS_WEIGHTS = {
    BLOCK_STATUS_APPROVED: 1.15,
    BLOCK_STATUS_DRAFT: 1.0,
    BLOCK_STATUS_DISPUTED: 0.82,
    BLOCK_STATUS_OUTDATED: 0.7,
    BLOCK_STATUS_REJECTED: 0.0,
    BLOCK_STATUS_WITHDRAWN: 0.0,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return fold_text(_text(value))


def _list_text(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in out:
            out.append(text)
    return out


def _context_key(block: dict[str, Any]) -> tuple[str, str, str]:
    subject_key = _norm(block.get("subject_key") or block.get("primary_subject"))
    space_key = _norm(block.get("space_key") or block.get("primary_space") or ",".join(_list_text(block.get("space_values"))))
    time_key = _norm(block.get("time_key") or block.get("primary_time") or ",".join(_list_text(block.get("time_values"))))
    return subject_key, space_key, time_key


def _assertion_signature(block: dict[str, Any]) -> set[str]:
    predicates = {_norm(item) for item in _list_text(block.get("predicates")) if _norm(item)}
    if predicates:
        return predicates
    text = _norm(block.get("text"))
    return {token for token in text.split() if len(token) >= 4}


def _manual_status(block: dict[str, Any]) -> str | None:
    metadata = block.get("metadata") if isinstance(block.get("metadata"), dict) else {}
    raw = _text(block.get("block_status") or metadata.get("block_status") or metadata.get("approval_status")).lower()
    return raw if raw in _STATUS_WEIGHTS else None


def _conflicts_for_block(block: dict[str, Any], existing_blocks: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    context_key = _context_key(block)
    if not context_key[0]:
        return []
    current_signature = _assertion_signature(block)
    conflicts: list[dict[str, Any]] = []
    for previous in existing_blocks:
        if _context_key(previous) != context_key:
            continue
        previous_id = _text(previous.get("id"))
        if previous_id and previous_id == _text(block.get("id")):
            continue
        previous_signature = _assertion_signature(previous)
        if current_signature and previous_signature and current_signature.intersection(previous_signature):
            continue
        previous_text = _norm(previous.get("text"))
        current_text = _norm(block.get("text"))
        if previous_text and current_text and previous_text == current_text:
            continue
        conflicts.append(
            {
                "block_id": previous_id,
                "source_id": previous.get("source_id"),
                "subject": previous.get("primary_subject"),
                "space": previous.get("primary_space"),
                "time": previous.get("primary_time"),
                "summary": previous.get("summary"),
                "reason": "same_subject_space_time_different_assertions",
            }
        )
        if len(conflicts) >= limit:
            break
    return conflicts


def enrich_semantic_blocks_with_quality(
    blocks: list[dict[str, Any]],
    *,
    existing_blocks: list[dict[str, Any]] | None = None,
    source_type: str | None = None,
) -> list[dict[str, Any]]:
    default_reliability = reliability_for_source_type(source_type)
    enriched_blocks: list[dict[str, Any]] = []
    previous_blocks = list(existing_blocks or [])
    for block in blocks:
        enriched = dict(block)
        metadata = dict(enriched.get("metadata") or {})
        conflicts = _conflicts_for_block(enriched, previous_blocks)
        manual_status = _manual_status(enriched)
        status = manual_status or (BLOCK_STATUS_DISPUTED if conflicts else BLOCK_STATUS_DRAFT)
        status_weight = _STATUS_WEIGHTS.get(status, 1.0)
        confidence = max(0.0, min(1.0, float(enriched.get("confidence") or 0.0)))
        reliability = (
            float(enriched.get("source_reliability") or 0.0)
            if source_type is None and enriched.get("source_reliability") is not None
            else default_reliability
        )
        reliability_weight = max(0.0, min(1.25, reliability))
        retrieval_weight = round(max(0.0, min(1.5, status_weight * (0.75 + (0.25 * confidence)) * reliability_weight)), 4)
        quality = {
            "block_status": status,
            "status_weight": round(status_weight, 4),
            "source_reliability": round(reliability, 4),
            "retrieval_weight": retrieval_weight,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "active_for_retrieval": status in _ACTIVE_STATUSES and retrieval_weight > 0,
        }
        metadata["block_quality"] = quality
        metadata["block_status"] = status
        enriched.update(
            {
                "block_status": status,
                "source_reliability": round(reliability, 4),
                "retrieval_weight": retrieval_weight,
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
                "metadata": metadata,
            }
        )
        enriched_blocks.append(enriched)
        previous_blocks.append(enriched)
    return enriched_blocks


__all__ = [
    "BLOCK_STATUS_APPROVED",
    "BLOCK_STATUS_DRAFT",
    "BLOCK_STATUS_DISPUTED",
    "BLOCK_STATUS_OUTDATED",
    "BLOCK_STATUS_REJECTED",
    "BLOCK_STATUS_WITHDRAWN",
    "enrich_semantic_blocks_with_quality",
]
