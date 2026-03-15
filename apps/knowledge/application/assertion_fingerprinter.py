from __future__ import annotations

import hashlib
from datetime import datetime


def _normalize_key(value: str) -> str:
    return (value or "").strip().lower()


def _coarse_time_bucket(value: datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    raw = str(value).strip()
    if len(raw) >= 10:
        return raw[:10]
    if len(raw) >= 7:
        return raw[:7]
    if len(raw) >= 4:
        return raw[:4]
    return raw


def build_assertion_fingerprint(
    kb_id: int,
    subject_key: str,
    predicate: str,
    object_key: str,
    time_bucket: str | datetime | None,
    place_key: str,
    modality: str = "asserted",
    polarity: str = "positive",
) -> str:
    """Assertion fingerprint deduplikációhoz és megerősítéshez."""
    raw = "|".join(
        [
            str(kb_id),
            _normalize_key(subject_key),
            _normalize_key(predicate),
            _normalize_key(object_key),
            _normalize_key(_coarse_time_bucket(time_bucket)),
            _normalize_key(place_key),
            _normalize_key(modality),
            _normalize_key(polarity),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]
