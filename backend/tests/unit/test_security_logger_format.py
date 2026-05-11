from __future__ import annotations

import json
import logging

import pytest

from core.kernel.logging.observability import clear_observability_context, set_request_id
from core.kernel.logging.security_logger import SecurityLogger


pytestmark = pytest.mark.unit


def test_security_logger_contains_required_structured_fields(caplog):
    clear_observability_context()
    set_request_id("req_abc123")
    logger = SecurityLogger()

    with caplog.at_level(logging.INFO, logger="security"):
        logger.emit_security_event(
            event="login_failed",
            level="WARNING",
            service="auth",
            message="Failed login attempt",
            user_id=None,
            ip="1.2.3.4",
            ua="Mozilla/5.0",
            email="user@example.com",
            country="HU",
            deviceId="device-1",
            riskScore=87,
            reason="bad_password",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].getMessage())
    for key in ("timestamp", "level", "event", "service", "requestId", "userId", "ip", "userAgent", "message"):
        assert key in payload
    assert payload["event"] == "login_failed"
    assert payload["service"] == "auth"
    assert payload["requestId"] == "req_abc123"
    assert payload["email"] == "user@example.com"
    assert payload["country"] == "HU"
    assert payload["deviceId"] == "device-1"
    assert payload["riskScore"] == 87
    assert payload["reason"] == "bad_password"

