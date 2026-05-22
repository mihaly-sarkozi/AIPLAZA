# backend/core/kernel/observability/metrics.py
# Feladat: Globális in-memory metrika registry köré ad egyszerű public helper API-t. Increment, observe, snapshot, reset és Prometheus render függvényeket biztosít, hogy a hívó kódnak ne kelljen registry példányt kezelnie. Core observability façade a runtime metrikákhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.kernel.observability.metric_registry import InMemoryMetricRegistry
from core.kernel.observability.prometheus_renderer import render_prometheus_metrics_from_registry


_metrics = InMemoryMetricRegistry()

def increment_metric(
    name: str,
    value: float = 1.0,
    *,
    unit: str = "count",
    tags: dict[str, Any] | None = None,
) -> None:
    _metrics.observe(name, value, unit=unit, tags=tags)


def observe_metric(
    name: str,
    value: float,
    *,
    unit: str = "count",
    tags: dict[str, Any] | None = None,
) -> None:
    _metrics.observe(name, value, unit=unit, tags=tags)


def get_metrics_snapshot() -> dict[str, dict[str, Any]]:
    return _metrics.snapshot()


def render_prometheus_metrics() -> str:
    return render_prometheus_metrics_from_registry(_metrics)


def reset_metrics() -> None:
    _metrics.reset()


__all__ = [
    "InMemoryMetricRegistry",
    "get_metrics_snapshot",
    "increment_metric",
    "observe_metric",
    "render_prometheus_metrics",
    "reset_metrics",
]
