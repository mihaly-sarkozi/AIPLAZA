# backend/core/kernel/observability/__init__.py
# Feladat: Az observability implementációs csomag belépési pontja. Jelenleg nem exportál összevont API-t, mert a compatibility façade a `core.kernel.logging.observability` alatt él, az implementációk pedig explicit modulokból importálhatók. Core csomagjelölő a context, metrics, payload és event logolási maghoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

__all__: list[str] = []
