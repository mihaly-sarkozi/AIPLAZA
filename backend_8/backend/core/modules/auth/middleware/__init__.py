# backend/core/modules/auth/middleware/__init__.py
# Feladat: Az auth middleware csomag exportfelülete. Az AuthMiddleware-t teszi elérhetővé a kernel HTTP middleware regisztráció számára, amely Bearer tokenből request.state.user értéket állít elő. Auth HTTP adapter csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .auth_middleware import AuthMiddleware

__all__ = ["AuthMiddleware"]
