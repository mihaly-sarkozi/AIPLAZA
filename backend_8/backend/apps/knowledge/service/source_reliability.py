from __future__ import annotations


SOURCE_RELIABILITY = {
    "official_doc": 1.0,
    "manual_confirmation": 1.2,
    "recent_user_feedback": 1.1,
    "old_note": 0.5,
    "auto_extracted": 0.7,
    "text": 0.8,
    "file": 0.9,
    "url": 0.8,
    "unknown": 0.4,
}


def reliability_for_source_type(source_type: str | None) -> float:
    return SOURCE_RELIABILITY.get(str(source_type or "unknown").strip().lower(), SOURCE_RELIABILITY["unknown"])


__all__ = ["SOURCE_RELIABILITY", "reliability_for_source_type"]
