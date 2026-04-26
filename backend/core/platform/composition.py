"""Backward-compat wrapper for platform composition.

Canonical definitions live in ``core.platform.contract.modules``.
"""
from __future__ import annotations

from core.platform.contract.modules import AppModule, ModuleContext

__all__ = ["AppModule", "ModuleContext"]
