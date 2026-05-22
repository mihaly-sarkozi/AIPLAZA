# backend/core/kernel/bootstrap/__init__.py
# Feladat: A bootstrap alkönyvtár csomagszintű belépési pontja. Szándékosan nem exportál konkrét buildereket, hogy a csomag importja könnyű maradjon, és a hívó mindig a pontos bootstrap modulból importáljon. A runtime wiring és az app container a konkrét submodule-okat használja, ezért ez csak import-határként fontos.
# Sárközi Mihály - 2026.05.21

"""Bootstrap internals package.

Keep this package import-light; import concrete helpers from submodules.
"""
from __future__ import annotations

__all__: list[str] = []
