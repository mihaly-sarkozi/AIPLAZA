from __future__ import annotations

# backend/apps/kb/kb_reading/storage/raw_refs.py
# Feladat: Nyers hivatkozás azonosítók építése.
# Sárközi Mihály - 2026.06.07

import re

from apps.kb.kb_reading.validation.ValidateFile import validate_file_name

_UNSAFE_REF_SEGMENT = re.compile(r"[/\\]+")


def _safe_segment(value: str) -> str:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    segment = str(value or "").strip()
    if not segment:
        raise ValueError("raw_ref segment must not be empty")
    cleaned = _UNSAFE_REF_SEGMENT.sub("_", segment)
    if cleaned in {".", ".."}:
        raise ValueError("invalid raw_ref segment")
    return cleaned


def sanitize_filename(filename: str) -> str:
    """Tisztítja a fájlnevet tárolás előtt."""
    return validate_file_name(filename)


def build_text_raw_ref(
    *,
    tenant: str,
    knowledge_base_id: str,
    read_run_id: str,
    read_item_id: str,
) -> str:
    """A modul egyik műveletét hajtja végre."""
    tenant_slug = _safe_segment(tenant or "default")
    kb_id = _safe_segment(knowledge_base_id)
    run_id = _safe_segment(read_run_id)
    item_id = _safe_segment(read_item_id)
    return f"tenants/{tenant_slug}/kb/{kb_id}/reading/{run_id}/{item_id}/input.txt"


def build_file_raw_ref(
    *,
    tenant: str,
    knowledge_base_id: str,
    read_run_id: str,
    read_item_id: str,
    filename: str,
) -> str:
    """A modul egyik műveletét hajtja végre."""
    tenant_slug = _safe_segment(tenant or "default")
    kb_id = _safe_segment(knowledge_base_id)
    run_id = _safe_segment(read_run_id)
    item_id = _safe_segment(read_item_id)
    safe_name = sanitize_filename(filename)
    return f"tenants/{tenant_slug}/kb/{kb_id}/reading/{run_id}/{item_id}/{safe_name}"


def build_url_raw_ref(
    *,
    tenant: str,
    knowledge_base_id: str,
    read_run_id: str,
    read_item_id: str,
) -> str:
    """A modul egyik műveletét hajtja végre."""
    tenant_slug = _safe_segment(tenant or "default")
    kb_id = _safe_segment(knowledge_base_id)
    run_id = _safe_segment(read_run_id)
    item_id = _safe_segment(read_item_id)
    return f"tenants/{tenant_slug}/kb/{kb_id}/reading/{run_id}/{item_id}/url_response"


__all__ = [
    "build_file_raw_ref",
    "build_text_raw_ref",
    "build_url_raw_ref",
    "sanitize_filename",
]
