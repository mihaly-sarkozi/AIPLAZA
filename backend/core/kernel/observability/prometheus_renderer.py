# backend/core/kernel/observability/prometheus_renderer.py
# Feladat: InMemoryMetricRegistry tartalmát Prometheus text exposition formátumra alakítja. Aggregált count, sum, last, p95, p99, max sorokat és natív histogram bucketeket renderel biztonságos metric és label nevekkel. Core observability export helper lifecycle vagy monitoring endpointokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.kernel.observability.metric_registry import InMemoryMetricRegistry, MetricSeries


def render_prometheus_metrics_from_registry(registry: InMemoryMetricRegistry) -> str:
    lines = [
        "# HELP aiplaza_metric_count Observed metric sample count.",
        "# TYPE aiplaza_metric_count counter",
        "# HELP aiplaza_metric_sum Observed metric sample sum.",
        "# TYPE aiplaza_metric_sum gauge",
        "# HELP aiplaza_metric_last Last observed metric sample.",
        "# TYPE aiplaza_metric_last gauge",
        "# HELP aiplaza_metric_p95 Approximate p95 from local samples.",
        "# TYPE aiplaza_metric_p95 gauge",
        "# HELP aiplaza_metric_p99 Approximate p99 from local samples.",
        "# TYPE aiplaza_metric_p99 gauge",
    ]
    for name, values in sorted(registry.snapshot().items()):
        labels = _prometheus_labels(name, values.get("tags"))
        lines.append(f"aiplaza_metric_count{{{labels}}} {float(values.get('count') or 0.0)}")
        lines.append(f"aiplaza_metric_sum{{{labels}}} {float(values.get('sum') or 0.0)}")
        lines.append(f"aiplaza_metric_last{{{labels}}} {float(values.get('last') or 0.0)}")
        lines.append(f"aiplaza_metric_p95{{{labels}}} {float(values.get('p95') or 0.0)}")
        lines.append(f"aiplaza_metric_p99{{{labels}}} {float(values.get('p99') or 0.0)}")
        if "max" in values:
            lines.append(f"aiplaza_metric_max{{{labels}}} {float(values.get('max') or 0.0)}")
    for series in sorted(registry.iter_series(), key=lambda item: (item.name, tuple(sorted(item.tags.items())))):
        lines.extend(_render_native_histogram_for_series(series))
    return "\n".join(lines) + "\n"


def _prometheus_name(name: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in str(name or "").strip().lower())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized or "unnamed"


def _prometheus_label_name(name: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in str(name or "").strip().lower())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized or "label"


def _prometheus_label_value(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


def _prometheus_labels(metric_name: str, tags: dict[str, Any] | None) -> str:
    labels: dict[str, str] = {"metric": _prometheus_name(metric_name)}
    for key, value in (tags or {}).items():
        label_key = _prometheus_label_name(key)
        labels[label_key] = _prometheus_label_value(value)
    return ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))


def _prometheus_series_labels(tags: dict[str, Any] | None) -> str:
    labels: dict[str, str] = {}
    for key, value in (tags or {}).items():
        labels[_prometheus_label_name(str(key))] = _prometheus_label_value(value)
    return ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))


def _render_native_histogram_for_series(series: MetricSeries) -> list[str]:
    base = f"aiplaza_{_prometheus_name(series.name)}"
    labels = _prometheus_series_labels(series.tags)
    lines = [
        f"# HELP {base} Histogram for metric '{series.name}'.",
        f"# TYPE {base} histogram",
    ]
    running = 0
    for idx, upper in enumerate(series.histogram_buckets):
        running += int(series.histogram_bucket_counts[idx])
        le_value = f"{upper:g}"
        if labels:
            lines.append(f'{base}_bucket{{{labels},le="{le_value}"}} {running}')
        else:
            lines.append(f'{base}_bucket{{le="{le_value}"}} {running}')
    if labels:
        lines.append(f'{base}_bucket{{{labels},le="+Inf"}} {int(series.count)}')
        lines.append(f"{base}_count{{{labels}}} {int(series.count)}")
        lines.append(f"{base}_sum{{{labels}}} {float(series.sum)}")
    else:
        lines.append(f'{base}_bucket{{le="+Inf"}} {int(series.count)}')
        lines.append(f"{base}_count {int(series.count)}")
        lines.append(f"{base}_sum {float(series.sum)}")
    return lines


__all__ = ["render_prometheus_metrics_from_registry"]
