# backend/shared/utils/datetime_utils.py
# Feladat: Datetime értékek közös UTC normalizálását végzi. Naive datetime esetén UTC tzinfót illeszt, aware datetimeot változatlanul hagy, így repository és response rétegek egységes időzóna-kezelést kapnak. Shared datetime utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import timezone


def normalize_utc_datetime(dt):
    """Attach UTC tzinfo to naive datetimes while leaving aware values untouched."""
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

__all__ = ["normalize_utc_datetime"]
