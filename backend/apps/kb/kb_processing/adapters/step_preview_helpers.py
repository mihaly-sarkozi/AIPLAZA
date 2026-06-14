from __future__ import annotations

_PREVIEW_LIMIT = 30
_TEXT_SNIPPET_LEN = 160


def text_snippet(value: str | None, *, max_len: int = _TEXT_SNIPPET_LEN) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 1].rstrip()}…"


def format_relation_label(node_type: str, node_id: str) -> str:
    raw = str(node_id or "").strip()
    if ":" in raw:
        prefix, label = raw.split(":", 1)
        if prefix == node_type or prefix in {"entity", "person", "company", "topic", "time", "location", "process"}:
            return label.strip() or raw
    return raw


__all__ = ["_PREVIEW_LIMIT", "format_relation_label", "text_snippet"]
