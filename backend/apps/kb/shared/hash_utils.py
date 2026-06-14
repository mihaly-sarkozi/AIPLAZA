from __future__ import annotations

import json
import uuid

from shared.utils.hash import sha256_text


def vector_hash(vector: list[float]) -> str:
    payload = ",".join(f"{v:.8f}" for v in vector)
    return sha256_text(payload)


def payload_hash(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(normalized)


def stable_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kb-chunk:{chunk_id}"))


__all__ = ["payload_hash", "stable_point_id", "vector_hash"]
