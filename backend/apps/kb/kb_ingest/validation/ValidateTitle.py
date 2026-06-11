from __future__ import annotations

# backend/apps/kb/kb_ingest/validation/ValidateTitle.py
# Feladat: Tanítási cím normalizálása.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.config.TrainingConf import DEFAULT_TRAINING_CONFIG, TrainingConfig


def normalize_title(
    value: str | None,
    *,
    fallback: str = "",
    config: TrainingConfig | None = None,
) -> str:
    """Normalizálja a címet; üres érték megengedett (megjelenítés a kliensen)."""
    cfg = config or DEFAULT_TRAINING_CONFIG
    normalized = str(value or "").strip()
    title = normalized or str(fallback or "").strip()
    return title[: cfg.max_title_length]


__all__ = ["normalize_title"]
