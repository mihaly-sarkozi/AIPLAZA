# backend/core/kernel/logging/telemetry.py
# Feladat: Runtime telemetry integrációkat kapcsol be best-effort módon. Settings alapján inicializálja a Sentryt és az OpenTelemetry FastAPI instrumentationt, dependency hiány esetén pedig csak warningot ír. Core observability bootstrap, amelyet az app factory hív az alkalmazás indításakor.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
from typing import Any

from core.kernel.config.config_loader import get_app_env

_log = logging.getLogger("core.telemetry")
_CONFIGURED = False


def configure_runtime_telemetry(settings: Any, app: Any) -> None:
    """Best-effort tracing/exception telemetry bootstrap.

    Külső dependency hiánya esetén nem dob hibát, csak strukturált warningot ír.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return
    _configure_sentry(settings)
    _configure_otel(settings, app)
    _CONFIGURED = True


def _configure_sentry(settings: Any) -> None:
    enabled = bool(getattr(settings, "sentry_enabled", False))
    dsn = str(getattr(settings, "sentry_dsn", "") or "").strip()
    if not enabled or not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception:
        _log.warning("Sentry init skipped: sentry-sdk dependency missing.")
        return
    env = str(getattr(settings, "sentry_environment", "") or "").strip() or get_app_env()
    traces_sample_rate = float(getattr(settings, "sentry_traces_sample_rate", 0.05) or 0.05)
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        traces_sample_rate=max(0.0, min(1.0, traces_sample_rate)),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        send_default_pii=False,
    )


def _configure_otel(settings: Any, app: Any) -> None:
    enabled = bool(getattr(settings, "observability_trace_enabled", False))
    if not enabled:
        return
    endpoint = str(getattr(settings, "observability_otlp_endpoint", "") or "").strip()
    service_name = str(getattr(settings, "observability_service_name", "aiplaza-backend") or "aiplaza-backend").strip()
    if not endpoint:
        _log.warning("OpenTelemetry init skipped: observability_otlp_endpoint missing.")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except Exception:
        _log.warning("OpenTelemetry init skipped: OTEL dependencies missing.")
        return
    sample_ratio = float(getattr(settings, "observability_trace_sample_ratio", 0.1) or 0.1)
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}),
        sampler=TraceIdRatioBased(max(0.0, min(1.0, sample_ratio))),
    )
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
