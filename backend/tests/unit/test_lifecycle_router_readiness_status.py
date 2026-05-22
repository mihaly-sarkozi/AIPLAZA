from __future__ import annotations

import pytest

from core.kernel.lifecycle.lifecycle_router import _should_return_unhealthy_status
from core.kernel.lifecycle.readiness_response import ReadinessResponse

pytestmark = pytest.mark.unit


def test_readiness_router_marks_not_ready_as_unhealthy() -> None:
    readiness = ReadinessResponse(status="not_ready", checks={"startup": "not_ready"})
    assert _should_return_unhealthy_status(readiness) is True


def test_readiness_router_allows_degraded_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.kernel.lifecycle.lifecycle_router.get_app_env", lambda: "test")
    readiness = ReadinessResponse(status="degraded", checks={"db": "ok"})
    assert _should_return_unhealthy_status(readiness) is False


def test_readiness_router_rejects_degraded_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.kernel.lifecycle.lifecycle_router.get_app_env", lambda: "production")
    readiness = ReadinessResponse(status="degraded", checks={"db": "ok"})
    assert _should_return_unhealthy_status(readiness) is True
