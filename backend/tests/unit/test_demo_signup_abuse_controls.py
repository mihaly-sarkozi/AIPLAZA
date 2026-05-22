from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.modules.tenant.signup import abuse_controls

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_demo_signup_enabled_fallback_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(abuse_controls, "get_redis", lambda: None)
    monkeypatch.setattr(abuse_controls, "_fallback_enabled_override", None)

    assert abuse_controls.is_demo_signup_enabled(default_enabled=True) is True

    abuse_controls.set_demo_signup_enabled(False)
    assert abuse_controls.is_demo_signup_enabled(default_enabled=True) is False


def test_bump_daily_counter_fallback_increments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(abuse_controls, "get_redis", lambda: None)
    monkeypatch.setattr(abuse_controls, "_fallback_counters", {})

    now = datetime(2026, 5, 9, tzinfo=timezone.utc)
    first = abuse_controls.bump_daily_counter(scope="ip", key="1.2.3.4", now=now)
    second = abuse_controls.bump_daily_counter(scope="ip", key="1.2.3.4", now=now)

    assert first == 1
    assert second == 2
