# backend/shared/utils/clock.py
# Feladat: Közös, tesztelhető UTC óra absztrakciót ad. A Clock protokoll, SystemClock implementáció és default clock setter/getter segítségével appok és core komponensek egységesen kérhetnek aktuális időpontot vagy dátumot. Shared időkezelési utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        ...


@dataclass(frozen=True)
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


_default_clock: Clock = SystemClock()


def set_default_clock(clock: Clock) -> None:
    global _default_clock
    _default_clock = clock


def get_default_clock() -> Clock:
    return _default_clock


def utc_now() -> datetime:
    return _default_clock.now()


def utc_today() -> date:
    return utc_now().date()


def utc_now_naive() -> datetime:
    return utc_now().replace(tzinfo=None)
