# backend/core/kernel/http/__init__.py
# Feladat: A kernel HTTP adapter csomag belépési pontja. Jelenleg nem exportál közvetlen API-t, mert a modulok explicit fájlokból importálnak dependency-ket, middleware regisztrációt és route kötést. Core csomagjelölő, amely a FastAPI integrációs réteget fogja össze.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

__all__: list[str] = []
