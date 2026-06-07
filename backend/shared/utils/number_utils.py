# backend/shared/utils/number_utils.py
# Feladat: Közös numerikus konverziókat tartalmaz. Pénz, tárhely és biztonságos int/string normalizálást ad domainfüggés nélkül.

from __future__ import annotations

import math
from typing import Any


def money_from_cents(cents: int) -> float:
    """Cent értéket két tizedesre kerekített pénzértékké alakít."""

    return round(int(cents) / 100.0, 2)


def round_storage_gb(storage_bytes: int | None) -> int:
    """Byte tárhelyhasználatot felfelé kerekített GB értékké alakít."""

    if not storage_bytes or storage_bytes <= 0:
        return 0
    return max(1, int(math.ceil(storage_bytes / (1024 ** 3))))


def non_negative_int(value: Any, default: int = 0) -> int:
    """Tetszőleges értéket nem negatív intté normalizál, hibánál defaulttal."""

    try:
        return max(0, int(value if value is not None else default))
    except (TypeError, ValueError):
        return max(0, int(default))


def string_or_default(value: Any, default: str) -> str:
    """Tetszőleges értéket stringgé alakít, üres/None esetén defaulttal."""

    return str(value or default)


__all__ = [
    "money_from_cents",
    "non_negative_int",
    "round_storage_gb",
    "string_or_default",
]
