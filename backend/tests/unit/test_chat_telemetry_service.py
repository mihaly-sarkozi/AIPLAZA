from __future__ import annotations

import pytest

from apps.chat.service import chat_telemetry_service as telemetry_module
from apps.chat.service.chat_telemetry_service import ChatTelemetryService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_chat_telemetry_records_timing_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics: list[tuple[str, float, dict | None]] = []
    observations: list[tuple[str, float, str | None, dict | None]] = []
    monkeypatch.setattr(telemetry_module, "increment_metric", lambda name, value=1.0, tags=None: metrics.append((name, value, tags)))
    monkeypatch.setattr(
        telemetry_module,
        "observe_metric",
        lambda name, value, unit=None, tags=None: observations.append((name, value, unit, tags)),
    )
    monkeypatch.setattr(telemetry_module, "perf_counter", lambda: 1.25)
    prompt_context = {"index_debug": {}}
    packet: dict = {}

    ChatTelemetryService().record_timing(
        packet=packet,
        context_build_ms=25.0,
        llm_ms=75.0,
        started_at=1.0,
        user_role="channel",
        kb_uuid="kb-1",
        context_text="context",
        context_failed=False,
        prompt_context=prompt_context,
        encoded_answer_text="encoded",
    )

    assert packet["_chat_timing_ms"] == {"context_build": 25.0, "llm": 75.0, "total": 250.0}
    assert prompt_context["encoded_answer_text"] == "encoded"
    assert prompt_context["index_debug"]["timing_ms"] == packet["_chat_timing_ms"]
    assert ("chat_requests_total", 1.0, {"channel": "channel"}) in metrics
    assert ("chat_latency_seconds", 0.25, "seconds", {"channel": "channel"}) in observations


def test_chat_telemetry_records_missing_ready_index(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics: list[tuple[str, float, dict | None]] = []
    events: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(telemetry_module, "increment_metric", lambda name, value=1.0, tags=None: metrics.append((name, value, tags)))
    monkeypatch.setattr(
        telemetry_module,
        "log_structured_event",
        lambda namespace, event, **kwargs: events.append((namespace, event, kwargs)),
    )

    ChatTelemetryService().record_missing_context_if_needed(
        packet={"no_ready_index_build": True, "kb_uuid": "kb-1", "build_ids": []},
        question="secret question",
        user_id=7,
        kb_uuid=None,
    )

    assert metrics == [("chat_missing_ready_index_detected_total", 1, None)]
    assert events[0][0] == "apps.chat"
    assert events[0][1] == "chat.context.empty_missing_ready_index"
    assert events[0][2]["kb_uuid"] == "kb-1"
    assert events[0][2]["user_id"] == 7
