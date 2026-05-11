from __future__ import annotations

import pytest

from core.kernel.logging.observability import observe_metric, render_prometheus_metrics, reset_metrics

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_prometheus_export_contains_metric_tags() -> None:
    reset_metrics()
    observe_metric(
        "platform.request.latency.ms",
        123.0,
        unit="ms",
        tags={"status_family": "2xx", "method": "GET", "path_group": "auth"},
    )

    payload = render_prometheus_metrics()

    assert 'metric="platform_request_latency_ms"' in payload
    assert 'status_family="2xx"' in payload
    assert 'method="GET"' in payload
    assert 'path_group="auth"' in payload


def test_prometheus_export_contains_native_histogram_series() -> None:
    reset_metrics()
    observe_metric("platform.request.latency.ms", 12.0, unit="ms", tags={"path_group": "auth"})
    observe_metric("platform.request.latency.ms", 30.0, unit="ms", tags={"path_group": "auth"})

    payload = render_prometheus_metrics()

    assert "# TYPE aiplaza_platform_request_latency_ms histogram" in payload
    assert 'aiplaza_platform_request_latency_ms_bucket{path_group="auth",le="25"} 1' in payload
    assert 'aiplaza_platform_request_latency_ms_bucket{path_group="auth",le="+Inf"} 2' in payload
    assert 'aiplaza_platform_request_latency_ms_count{path_group="auth"} 2' in payload


def test_prometheus_export_keeps_distinct_tag_series() -> None:
    reset_metrics()
    observe_metric("platform.request.latency.ms", 20.0, unit="ms", tags={"path_group": "auth"})
    observe_metric("platform.request.latency.ms", 50.0, unit="ms", tags={"path_group": "chat"})

    payload = render_prometheus_metrics()

    assert 'aiplaza_platform_request_latency_ms_count{path_group="auth"} 1' in payload
    assert 'aiplaza_platform_request_latency_ms_count{path_group="chat"} 1' in payload
