# backend/apps/billing/debug_clock.py
# Feladat: Billing dátumszimulációhoz használható Clock wrapper. Normál esetben a base clock aktuális idejét adja, debug módban pedig a beállított dátumot kombinálja az aktuális időkomponenssel. Program-specifikus debug időkezelési adapter.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import date, datetime

from shared.utils.clock import Clock


class BillingDebugClock:
    def __init__(self, base_clock: Clock) -> None:
        self._base_clock = base_clock
        self._simulated_date: date | None = None

    def now(self) -> datetime:
        current = self._base_clock.now()
        if self._simulated_date is None:
            return current
        return datetime.combine(self._simulated_date, current.timetz())

    def set_simulated_date(self, value: date | None) -> None:
        self._simulated_date = value

    @property
    def simulated_date(self) -> date | None:
        return self._simulated_date


__all__ = ["BillingDebugClock"]
