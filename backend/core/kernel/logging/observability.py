from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import threading
import traceback
from dataclasses import dataclass, field
from contextlib import contextmanager
from typing import Any

from core.kernel.config.instance_role import get_instance_role
from core.kernel.clock import utc_now
from shared.utils import sanitize_log_data

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "observability_context",
    default={},
)


def _utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass
class _MetricSeries:
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
        self._stats: dict[tuple[str, tuple[tuple[str, str], ...]], _MetricSeries] = {}
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
                current = _MetricSeries(
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
            return {
                name: dict(values)
                for name, values in aggregated.items()
            }

    def iter_series(self) -> list[_MetricSeries]:
        with self._lock:
            return [
                _MetricSeries(
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


_metrics = InMemoryMetricRegistry()
_SAFE_FIELD_NAMES = frozenset(
    {
        "actor_type",
        "auth_outcome",
        "batch_id",
        "claimed_count",
        "component",
        "correlation_id",
        "db_query_count",
        "db_query_total_ms",
        "elapsed_ms",
        "error_type",
        "error_message",
        "event_id",
        "event_name",
        "event",
        "service",
        "requestId",
        "userId",
        "userAgent",
        "deviceId",
        "riskScore",
        "event_type",
        "country",
        "reason",
        "idempotency_key",
        "instance_role",
        "level",
        "lock_owner",
        "logger",
        "message",
        "method",
        "mode",
        "outcome",
        "path",
        "request_id",
        "response_started",
        "retry_count",
        "stale_lock_after_sec",
        "status_code",
        "tenant_id",
        "tenant_resolution_outcome",
        "tenant_slug",
        "timeout_sec",
        "timestamp",
        "total_ms",
        "traceback",
        "user_id",
        "worker_role",
        "worker_run_id",
    }
)


def get_observability_context() -> dict[str, Any]:
    return dict(_context.get())


def bind_observability_context(**fields: Any):
    current = get_observability_context()
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    return _context.set(current)


def reset_observability_context(token) -> None:
    _context.reset(token)


@contextmanager
def observability_scope(**fields: Any):
    token = bind_observability_context(**fields)
    try:
        yield
    finally:
        reset_observability_context(token)


def set_correlation_id(value: str | None) -> None:
    bind_observability_context(correlation_id=(value or "").strip() or None)


def set_request_id(value: str | None) -> None:
    bind_observability_context(request_id=(value or "").strip() or None)


def set_tenant_context(*, tenant_id: int | None = None, tenant_slug: str | None = None) -> None:
    bind_observability_context(tenant_id=tenant_id, tenant_slug=tenant_slug)


def set_user_id(value: int | None) -> None:
    bind_observability_context(user_id=value)


def get_correlation_id() -> str | None:
    value = get_observability_context().get("correlation_id")
    return str(value) if value else None


def get_request_id() -> str | None:
    value = get_observability_context().get("request_id")
    return str(value) if value else None


def clear_correlation_id() -> None:
    bind_observability_context(correlation_id=None, request_id=None)


def clear_observability_context() -> None:
    _context.set({})


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
    ordered = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
    return ordered


def _prometheus_series_labels(tags: dict[str, Any] | None) -> str:
    labels: dict[str, str] = {}
    for key, value in (tags or {}).items():
        labels[_prometheus_label_name(str(key))] = _prometheus_label_value(value)
    return ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))


def _render_native_histogram_for_series(series: _MetricSeries) -> list[str]:
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


def render_prometheus_metrics() -> str:
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
    for name, values in sorted(get_metrics_snapshot().items()):
        labels = _prometheus_labels(name, values.get("tags"))
        lines.append(f"aiplaza_metric_count{{{labels}}} {float(values.get('count') or 0.0)}")
        lines.append(f"aiplaza_metric_sum{{{labels}}} {float(values.get('sum') or 0.0)}")
        lines.append(f"aiplaza_metric_last{{{labels}}} {float(values.get('last') or 0.0)}")
        lines.append(f"aiplaza_metric_p95{{{labels}}} {float(values.get('p95') or 0.0)}")
        lines.append(f"aiplaza_metric_p99{{{labels}}} {float(values.get('p99') or 0.0)}")
        if "max" in values:
            lines.append(f"aiplaza_metric_max{{{labels}}} {float(values.get('max') or 0.0)}")
    for series in sorted(_metrics.iter_series(), key=lambda item: (item.name, tuple(sorted(item.tags.items())))):
        lines.extend(_render_native_histogram_for_series(series))
    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    _metrics.reset()


def _default_log_context() -> dict[str, Any]:
    context = get_observability_context()
    if "instance_role" not in context:
        try:
            context["instance_role"] = get_instance_role().value
        except Exception:
            context["instance_role"] = None
    return context


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, BaseException):
            return str(value)
        return repr(value)


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SAFE_FIELD_NAMES or key.endswith(("_id", "_ms", "_count")):
            if isinstance(value, dict):
                sanitized[key] = {nested_key: _json_safe(nested_value) for nested_key, nested_value in value.items()}
            else:
                sanitized[key] = value
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value) or {}
            continue
        maybe_sanitized = sanitize_log_data({key: value}) or {}
        sanitized[key] = maybe_sanitized.get(key)
    return sanitized


def log_structured_event(
    logger_name: str,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event_name": event,
        "timestamp": _utc_now_iso(),
    }
    payload.update(_default_log_context())
    for key, value in fields.items():
        if value is not None:
            payload[key] = _json_safe(value)
    payload = _sanitize_payload(payload)
    logging.getLogger(logger_name).log(level, "%s", json.dumps(payload, ensure_ascii=False, sort_keys=True))


def log_exception_event(
    logger_name: str,
    event: str,
    error: BaseException,
    *,
    level: int = logging.ERROR,
    include_traceback: bool = True,
    **fields: Any,
) -> None:
    payload = {
        **fields,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if include_traceback:
        payload["traceback"] = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    log_structured_event(logger_name, event, level=level, **payload)


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "component": record.name,
        }
        payload.update(_default_log_context())

        message = record.getMessage()
        structured_message: dict[str, Any] | None = None
        if message:
            try:
                maybe_json = json.loads(message)
                if isinstance(maybe_json, dict):
                    structured_message = maybe_json
            except Exception:
                structured_message = None

        if structured_message is not None:
            payload.update(structured_message)
        elif message:
            payload["message"] = message

        if record.exc_info:
            exc_type, exc, _ = record.exc_info
            payload["error_type"] = exc_type.__name__ if exc_type else None
            payload["error_message"] = str(exc) if exc else message
            payload["traceback"] = self.formatException(record.exc_info)

        payload = _sanitize_payload(payload)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_structured_logging(*, level: int | None = None) -> None:
    effective_level = level
    if effective_level is None:
        raw = os.environ.get("LOG_LEVEL") or "INFO"
        effective_level = getattr(logging, raw.strip().upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredJsonFormatter())
    logging.basicConfig(level=effective_level, handlers=[handler], force=True)


__all__ = [
    "bind_observability_context",
    "clear_correlation_id",
    "clear_observability_context",
    "configure_structured_logging",
    "get_correlation_id",
    "get_observability_context",
    "get_metrics_snapshot",
    "get_request_id",
    "increment_metric",
    "log_exception_event",
    "log_structured_event",
    "observe_metric",
    "observability_scope",
    "reset_observability_context",
    "reset_metrics",
    "render_prometheus_metrics",
    "set_correlation_id",
    "set_request_id",
    "set_tenant_context",
    "set_user_id",
]
