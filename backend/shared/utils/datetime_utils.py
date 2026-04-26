# Ez a fájl több modul által közösen használt backend segédlogikát tartalmaz.
from __future__ import annotations

from datetime import timezone


def normalize_utc_datetime(dt):
    """Attach UTC tzinfo to naive datetimes while leaving aware values untouched."""
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

__all__ = ["normalize_utc_datetime"]
