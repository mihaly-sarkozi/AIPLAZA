from __future__ import annotations

# backend/apps/kb/module.py
# Feladat: Egységes app modul entrypoint (platform konvenció).
# Sárközi Mihály - 2026.06.11

from apps.kb.bootstrap.app_module import KbAppModule as _KbAppModule
from core.kernel.interface import BaseAppModule


class KbModule(_KbAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return KbModule()


__all__ = ["KbModule", "get_module"]
