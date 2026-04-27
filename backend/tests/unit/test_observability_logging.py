from __future__ import annotations

import json
import logging

from core.kernel.logging.observability import (
    bind_observability_context,
    clear_correlation_id,
    get_metrics_snapshot,
    log_structured_event,
    reset_metrics,
    reset_observability_context,
    render_prometheus_metrics,
    set_correlation_id,
)
from core.kernel.logging.request_timing import clear_request_timing, init_request_timing, record_db_query, record_span


def test_structured_log_includes_correlation_id(caplog):
    clear_correlation_id()
    set_correlation_id("req-123")

    with caplog.at_level(logging.INFO, logger="core.test"):
        log_structured_event("core.test", "test.event", foo="bar")

    payload = json.loads(caplog.records[-1].message)
    assert payload["event_name"] == "test.event"
    assert payload["correlation_id"] == "req-123"
    assert payload["foo"] == "bar"

    clear_correlation_id()


def test_request_timing_records_platform_metrics():
    reset_metrics()
    init_request_timing()

    record_span("tenant_resolve", 12.5)
    record_span("auth_total", 22.0)
    record_db_query(3.75)

    snapshot = get_metrics_snapshot()

    assert snapshot["platform.tenant.resolve.ms"]["count"] == 1
    assert snapshot["platform.auth.total.ms"]["count"] == 1
    assert snapshot["platform.db.query.ms"]["count"] == 1
    assert snapshot["platform.db.query.count"]["sum"] == 1.0

    clear_request_timing()
    reset_metrics()


def test_prometheus_metrics_export_uses_text_format():
    reset_metrics()
    init_request_timing()

    record_span("tenant_resolve", 12.5)
    body = render_prometheus_metrics()

    assert "# TYPE aiplaza_metric_count counter" in body
    assert 'aiplaza_metric_count{metric="platform_tenant_resolve_ms"} 1.0' in body
    assert 'aiplaza_metric_sum{metric="platform_tenant_resolve_ms"} 12.5' in body

    clear_request_timing()
    reset_metrics()


def test_structured_log_sanitizes_sensitive_fields(caplog):
    token = bind_observability_context(correlation_id="corr-1", request_id="req-1")
    try:
        with caplog.at_level(logging.INFO, logger="core.test"):
            log_structured_event(
                "core.test",
                "security.test",
                password="secret",
                email="teszt@example.com",
                nested={"refresh_token": "abc", "safe": "ok"},
            )
    finally:
        reset_observability_context(token)

    payload = json.loads(caplog.records[-1].message)
    assert payload["request_id"] == "req-1"
    assert payload["password"] == "[REDACTED]"
    assert payload["email"] == "te***@******e.com"
    assert payload["nested"]["refresh_token"] == "[REDACTED]"
    assert payload["nested"]["safe"] == "ok"
