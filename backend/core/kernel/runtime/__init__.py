# backend/core/kernel/runtime/__init__.py
# Feladat: A kernel runtime belső csomag belépési pontja. Nem exportál eager API-t, mert a wiring modulok importja assembly függőségeket húzhat be; konkrét runtime elemeket explicit almodulból kell importálni. Core futásidejű szervezési csomag, amely az AppContainer összerakását támogatja.
# Sárközi Mihály - 2026.05.21

"""Runtime internals package.

Import concrete runtime types from submodules to avoid eager assembly loads.
"""
from __future__ import annotations

__all__: list[str] = []
