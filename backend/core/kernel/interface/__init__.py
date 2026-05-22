# backend/core/kernel/interface/__init__.py
# Feladat: A kernel stabil, olcsón importálható public interface exportfelülete. Csak a modulfejlesztéshez szükséges alap szerződéseket adja ki: BaseAppModule, ModuleContext és RouteRegistration. Core framework boundary, amelyet app modulok közvetlenül importálhatnak.
# Sárközi Mihály - 2026.05.21

"""Platform interface public API.

Only the stable platform module/routing primitives are exported here.
Keep imports from this package cheap and runtime-free.
"""
from __future__ import annotations

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.routing import RouteRegistration


__all__ = [
    "BaseAppModule",
    "ModuleContext",
    "RouteRegistration",
]
