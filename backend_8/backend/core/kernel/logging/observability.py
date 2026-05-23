# backend/core/kernel/logging/observability.py
# Feladat: Kompatibilis exportfelület a külön `core.kernel.observability` modulokra bontott context, event és metrics API-khoz. Régi importútvonalat tart meg HTTP, DB, events és modul kódok számára, miközben az implementáció már dedikált observability csomagban él. Core compatibility facade, amely fokozatos átállást tesz lehetővé.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.logging.logging_config import configure_structured_logging
from core.kernel.observability.context import (
    bind_observability_context,
    clear_correlation_id,
    clear_observability_context,
    get_correlation_id,
    get_observability_context,
    get_request_id,
    observability_scope,
    reset_observability_context,
    set_correlation_id,
    set_request_id,
    set_tenant_context,
    set_user_id,
)
from core.kernel.observability.events import log_exception_event, log_structured_event
from core.kernel.observability.metrics import (
    InMemoryMetricRegistry,
    get_metrics_snapshot,
    increment_metric,
    observe_metric,
    render_prometheus_metrics,
    reset_metrics,
)

__all__ = [
    "InMemoryMetricRegistry",
    "bind_observability_context",
    "clear_correlation_id",
    "clear_observability_context",
    "configure_structured_logging",
    "get_correlation_id",
    "get_metrics_snapshot",
    "get_observability_context",
    "get_request_id",
    "increment_metric",
    "log_exception_event",
    "log_structured_event",
    "observe_metric",
    "observability_scope",
    "render_prometheus_metrics",
    "reset_metrics",
    "reset_observability_context",
    "set_correlation_id",
    "set_request_id",
    "set_tenant_context",
    "set_user_id",
]
