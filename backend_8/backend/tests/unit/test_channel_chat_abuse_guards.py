from __future__ import annotations

import asyncio
from contextlib import nullcontext

import pytest

import apps.chat.application.channel_session_policy as channel_support
from apps.chat.channel_access import ChannelAccessRepository

pytestmark = pytest.mark.unit


def test_session_quota_isolated_by_session_key() -> None:
    repo = ChannelAccessRepository(lambda: nullcontext(None))

    allowed1, _, _ = repo.reserve_usage_slot(
        tenant_id=1,
        credential_id=10,
        daily_limit=100,
        per_minute_limit=100,
        session_key="session-a",
        session_per_minute_limit=1,
        session_burst_10s_limit=1,
    )
    allowed2, reason2, _ = repo.reserve_usage_slot(
        tenant_id=1,
        credential_id=10,
        daily_limit=100,
        per_minute_limit=100,
        session_key="session-a",
        session_per_minute_limit=1,
        session_burst_10s_limit=1,
    )
    allowed3, _, _ = repo.reserve_usage_slot(
        tenant_id=1,
        credential_id=10,
        daily_limit=100,
        per_minute_limit=100,
        session_key="session-b",
        session_per_minute_limit=1,
        session_burst_10s_limit=1,
    )

    assert allowed1 is True
    assert allowed2 is False
    assert "munkamenetből" in str(reason2).lower()
    assert allowed3 is True


@pytest.mark.release_acceptance
def test_session_pacing_returns_retry_after_for_too_fast_requests(monkeypatch) -> None:
    monkeypatch.setattr(channel_support, "get_rate_limit_redis", lambda: None)
    monkeypatch.setattr(
        channel_support,
        "channel_session_limits",
        lambda: {
            "session_per_minute": 30,
            "session_burst_10s": 5,
            "session_min_interval_ms": 5000,
            "session_wait_max_ms": 0,
            "session_cookie_max_age_sec": 86400,
        },
    )
    with channel_support.channel_session_lock:
        channel_support.channel_session_last_seen_ms.clear()

    first = asyncio.run(
        channel_support.apply_channel_session_pacing(
            tenant_id=1,
            credential_id=10,
            session_id="session-a",
        )
    )
    second = asyncio.run(
        channel_support.apply_channel_session_pacing(
            tenant_id=1,
            credential_id=10,
            session_id="session-a",
        )
    )

    assert first[0] is True
    assert second[0] is False
    assert int(second[1]) >= 1
