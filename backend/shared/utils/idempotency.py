from __future__ import annotations

# backend/shared/utils/idempotency.py
# Feladat: Ismétlésmentes kulcs építése tartalom-alapú műveletekhez.
# Sárközi Mihály - 2026.06.07

DEFAULT_IDEMPOTENCY_PIPELINE_VERSION = "reading.v1"


def build_idempotency_key(
    *,
    knowledge_base_id: str,
    content_hash: str,
    pipeline_version: str = DEFAULT_IDEMPOTENCY_PIPELINE_VERSION,
) -> str:
    """Ismétlésmentes kulcs: tudástár + pipeline verzió + tartalom lenyomat."""
    kb_id = str(knowledge_base_id or "").strip()
    digest = str(content_hash or "").strip()
    version = str(pipeline_version or DEFAULT_IDEMPOTENCY_PIPELINE_VERSION).strip()
    return f"{kb_id}:{version}:{digest}"


def content_hash_from_idempotency_key(idempotency_key: str) -> str | None:
    """A build_idempotency_key formátumú kulcsból kinyeri a tartalom lenyomatot."""
    key = str(idempotency_key or "").strip()
    if not key:
        return None
    parts = key.split(":")
    if len(parts) < 3:
        return None
    digest = parts[-1].strip()
    return digest or None


__all__ = [
    "DEFAULT_IDEMPOTENCY_PIPELINE_VERSION",
    "build_idempotency_key",
    "content_hash_from_idempotency_key",
]
