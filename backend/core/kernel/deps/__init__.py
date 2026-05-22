# backend/core/kernel/deps/__init__.py
# Feladat: A deps könyvtár csomagszintű kompatibilitási exportját adja. A facade.py public API-ját re-exportálja, hogy a rövid `core.kernel.deps` importútvonal továbbra is működjön. A konkrét használóknak elsősorban a `core.kernel.deps.facade` stabil belépési pont ajánlott.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .facade import *  # noqa: F401,F403
