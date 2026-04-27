from __future__ import annotations

from typing import Any


RETRIEVAL_CHUNK_INDEX_VERSION = "retrieval_chunk_index_v0"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(items: list[str], value: Any) -> None:
    text = _text(value)
    if text and text not in items:
        items.append(text)


def _claims(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    structured = chunk.get("structured_facts") if isinstance(chunk.get("structured_facts"), dict) else {}
    out: list[dict[str, Any]] = []
    for bucket in ("current", "active", "conflicts", "historical", "descriptors", "events", "relations", "rules"):
        for item in structured.get(bucket) or []:
            if isinstance(item, dict):
                claim = dict(item)
                claim.setdefault("fact_bucket", bucket)
                out.append(claim)
    return out


def _claim_types(chunk: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for claim in _claims(chunk):
        _append_unique(out, claim.get("claim_group"))
        _append_unique(out, claim.get("claim_type"))
        _append_unique(out, claim.get("fact_bucket"))
    return out


def _states(chunk: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for claim in _claims(chunk):
        predicate = _text(claim.get("predicate") or claim.get("predicate_text")).lower()
        obj = _text(claim.get("object") or claim.get("object_text")).lower()
        if predicate == "active" and obj in {"true", "active", "yes"}:
            _append_unique(out, "active")
        if predicate == "active" and obj in {"false", "inactive", "no"}:
            _append_unique(out, "inactive")
    return out


def _time_modes(chunk: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for claim in _claims(chunk):
        _append_unique(out, claim.get("time_dominant"))
        _append_unique(out, claim.get("time_mode"))
        if _text(claim.get("status")).lower() == "historical":
            _append_unique(out, "historical")
    return out


def _metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "profile_id": chunk.get("profile_id"),
        "canonical_key": chunk.get("canonical_key"),
        "retrieval_chunk_id": chunk.get("retrieval_chunk_id"),
        "retrieval_chunk_text": chunk.get("retrieval_chunk_text"),
        "structured_facts": chunk.get("structured_facts") or {},
        "evidence_ids": list(chunk.get("evidence_ids") or []),
        "source_ids": list(chunk.get("source_ids") or []),
        "conflicting": bool(chunk.get("conflicting")),
        "temporal_context_included": bool(chunk.get("temporal_context_included")),
        "builder_version": chunk.get("builder_version"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def build_retrieval_chunk_index_rows(
    retrieval_chunks: list[dict[str, Any]],
    *,
    build_id: str,
    index_profile_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in retrieval_chunks:
        if not isinstance(chunk, dict):
            continue
        profile_id = _text(chunk.get("profile_id"))
        text = _text(chunk.get("retrieval_chunk_text"))
        if not profile_id or not text:
            continue
        metadata = _metadata(chunk)
        rows.append(
            {
                "id": profile_id,
                "text": text,
                "payload": {
                    "profile_id": profile_id,
                    "entity_name": chunk.get("entity_name"),
                    "entity_type": chunk.get("entity_type") or metadata.get("entity_type"),
                    "canonical_key": chunk.get("canonical_key"),
                    "claim_types": _claim_types(chunk),
                    "states": _states(chunk),
                    "time_modes": _time_modes(chunk),
                    "metadata": metadata,
                    "text": text,
                    "build_id": build_id,
                    "index_profile_key": index_profile_key,
                },
            }
        )
    return rows


__all__ = ["RETRIEVAL_CHUNK_INDEX_VERSION", "build_retrieval_chunk_index_rows"]
