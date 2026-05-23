# backend/core/kernel/runtime/clock.py
# Feladat: A platform közös clock dependency-jét és idő helperjeit re-exportálja. Core és app modulok innen használják a Clock, SystemClock, utc_now, utc_now_naive és utc_today API-kat, hogy az időkezelés egységes és tesztelhető maradjon. Core runtime dependency, amely public API-ként is engedélyezett.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from shared.utils.clock import (
    Clock,
    SystemClock,
    get_default_clock,
    set_default_clock,
    utc_now,
    utc_now_naive,
    utc_today,
)

__all__ = [
    "Clock",
    "SystemClock",
    "get_default_clock",
    "set_default_clock",
    "utc_now",
    "utc_now_naive",
    "utc_today",
]
