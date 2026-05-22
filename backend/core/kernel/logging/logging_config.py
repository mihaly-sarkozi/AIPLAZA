# backend/core/kernel/logging/logging_config.py
# Feladat: A Python logging globális strukturált JSON konfigurációját állítja be. A log szintet explicit paraméterből vagy settingsből kapott névből vezeti le, majd a StructuredJsonFormattert köti stderr streamre. Core runtime logging bootstrap, amelyet az app factory és a standalone worker entrypoint használ.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import sys

from core.kernel.logging.structured_formatter import StructuredJsonFormatter


def configure_structured_logging(*, level: int | None = None, level_name: str | None = None) -> None:
    effective_level = level
    if effective_level is None:
        raw = (level_name or "INFO").strip().upper()
        effective_level = getattr(logging, raw, logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredJsonFormatter())
    logging.basicConfig(level=effective_level, handlers=[handler], force=True)


__all__ = ["configure_structured_logging"]
