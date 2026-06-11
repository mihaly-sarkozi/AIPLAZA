from __future__ import annotations

# backend/apps/kb/kb_ingest/config/MetricsConf.py
# Feladat: Tanítási metrikák rögzítése (jelenleg no-op; később observability bekötés).
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.enums.TrainingMetric import TrainingMetric


def increment(
    metric: TrainingMetric,
    value: float = 1.0,
    **tags: str,
) -> None:
    _ = (metric.value, value, tags)


__all__ = ["increment"]
