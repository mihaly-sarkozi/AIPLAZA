# backend/core/kernel/observability/metric_registry.py
# Feladat: Thread-safe in-memory metrika registryt és MetricSeries adatmodellt tartalmaz. Count, sum, min, max, last, p95/p99 minták és histogram bucketek gyűjtését végzi név és tag kombináció szerint. Core observability infrastruktúra fejlesztői, teszt és lightweight runtime metrikákhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricSeries:
    name: str
    unit: str
    tags: dict[str, Any] = field(default_factory=dict)
    count: int = 0
    sum: float = 0.0
    min: float = 0.0
    max: float = 0.0
    last: float = 0.0
    values: list[float] = field(default_factory=list)
    histogram_buckets: tuple[float, ...] = field(default_factory=tuple)
    histogram_bucket_counts: list[int] = field(default_factory=list)


class InMemoryMetricRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: dict[tuple[str, tuple[tuple[str, str], ...]], MetricSeries] = {}
        self._max_samples_per_series = 2048
        self._histogram_buckets_by_unit: dict[str, tuple[float, ...]] = {
            "ms": (5.0, 10.0, 25.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0, 750.0, 1000.0, 2000.0, 5000.0, 10000.0),
            "count": (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 5000.0),
            "usd": (0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0),
            "tokens": (10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0, 20000.0),
            "bytes": (256.0, 1024.0, 4096.0, 16384.0, 65536.0, 262144.0, 1048576.0, 5242880.0, 10485760.0),
        }
        raw_ms = str(
            os.environ.get("OBSERVABILITY_METRICS_HISTOGRAM_BUCKETS_MS")
            or os.environ.get("observability_metrics_histogram_buckets_ms")
            or ""
        ).strip()
        if raw_ms:
            try:
                parsed = tuple(float(item.strip()) for item in raw_ms.split(",") if item.strip())
                if parsed and all(value > 0 for value in parsed):
                    self._histogram_buckets_by_unit["ms"] = tuple(sorted(parsed))
            except Exception:
                pass

    @staticmethod
    def _normalize_tags(tags: dict[str, Any] | None) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in (tags or {}).items():
            normalized[str(key)] = str(value)
        return normalized

    def _series_key(self, name: str, tags: dict[str, Any] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
        normalized_tags = self._normalize_tags(tags)
        return str(name), tuple(sorted(normalized_tags.items()))

    def _series_buckets(self, unit: str) -> tuple[float, ...]:
        normalized = str(unit or "count").strip().lower()
        return self._histogram_buckets_by_unit.get(normalized, self._histogram_buckets_by_unit["count"])

    @staticmethod
    def _quantile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])
        sorted_values = sorted(values)
        position = ratio * (len(sorted_values) - 1)
        lower_idx = int(position)
        upper_idx = min(lower_idx + 1, len(sorted_values) - 1)
        if lower_idx == upper_idx:
            return float(sorted_values[lower_idx])
        weight = position - lower_idx
        return float(sorted_values[lower_idx] * (1.0 - weight) + sorted_values[upper_idx] * weight)

    def observe(
        self,
        name: str,
        value: float,
        *,
        unit: str = "count",
        tags: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            series_key = self._series_key(name, tags)
            current = self._stats.get(series_key)
            if current is None:
                normalized_tags = self._normalize_tags(tags)
                buckets = self._series_buckets(unit)
                current = MetricSeries(
                    name=str(name),
                    unit=str(unit or "count"),
                    tags=normalized_tags,
                    count=0,
                    sum=0.0,
                    min=float(value),
                    max=float(value),
                    last=float(value),
                    values=[],
                    histogram_buckets=buckets,
                    histogram_bucket_counts=[0 for _ in buckets],
                )
                self._stats[series_key] = current
            current.count += 1
            current.sum += float(value)
            current.min = min(float(current.min), float(value))
            current.max = max(float(current.max), float(value))
            current.last = float(value)
            current.values.append(float(value))
            if len(current.values) > self._max_samples_per_series:
                current.values.pop(0)
            for idx, upper in enumerate(current.histogram_buckets):
                if float(value) <= upper:
                    current.histogram_bucket_counts[idx] += 1

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            aggregated: dict[str, dict[str, Any]] = {}
            for series in self._stats.values():
                current = aggregated.get(series.name)
                if current is None:
                    current = {
                        "count": 0,
                        "sum": 0.0,
                        "min": float(series.min),
                        "max": float(series.max),
                        "last": float(series.last),
                        "unit": series.unit,
                        "tags": dict(series.tags),
                        "_samples": [],
                    }
                    aggregated[series.name] = current
                current["count"] += int(series.count)
                current["sum"] += float(series.sum)
                current["min"] = min(float(current["min"]), float(series.min))
                current["max"] = max(float(current["max"]), float(series.max))
                current["last"] = float(series.last)
                current["_samples"].extend(series.values)
            for values in aggregated.values():
                samples = list(values.pop("_samples", []))
                values["p95"] = self._quantile(samples, 0.95)
                values["p99"] = self._quantile(samples, 0.99)
            return {name: dict(values) for name, values in aggregated.items()}

    def iter_series(self) -> list[MetricSeries]:
        with self._lock:
            return [
                MetricSeries(
                    name=series.name,
                    unit=series.unit,
                    tags=dict(series.tags),
                    count=int(series.count),
                    sum=float(series.sum),
                    min=float(series.min),
                    max=float(series.max),
                    last=float(series.last),
                    values=list(series.values),
                    histogram_buckets=tuple(series.histogram_buckets),
                    histogram_bucket_counts=list(series.histogram_bucket_counts),
                )
                for series in self._stats.values()
            ]

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


__all__ = ["InMemoryMetricRegistry", "MetricSeries"]
