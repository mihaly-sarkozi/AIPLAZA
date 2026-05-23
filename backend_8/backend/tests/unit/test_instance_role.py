from __future__ import annotations

import pytest

from core.kernel.runtime.instance_role import (
    InstanceRole,
    get_instance_role,
    should_run_background_workers,
    should_run_standalone_billing_worker,
    should_run_standalone_outbox_worker,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_should_run_background_workers_only_in_combined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTANCE_ROLE", InstanceRole.COMBINED.value)
    assert should_run_background_workers() is True

    monkeypatch.setenv("INSTANCE_ROLE", InstanceRole.WEB.value)
    assert should_run_background_workers() is False

    monkeypatch.setenv("INSTANCE_ROLE", InstanceRole.WORKER.value)
    assert should_run_background_workers() is False


def test_should_run_standalone_worker_loops_respect_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTANCE_ROLE", InstanceRole.WORKER.value)
    monkeypatch.delenv("OUTBOX_WORKER_LOOP_ENABLED", raising=False)
    monkeypatch.delenv("BILLING_WORKER_LOOP_ENABLED", raising=False)
    assert should_run_standalone_outbox_worker() is True
    assert should_run_standalone_billing_worker() is True

    monkeypatch.setenv("OUTBOX_WORKER_LOOP_ENABLED", "false")
    monkeypatch.setenv("BILLING_WORKER_LOOP_ENABLED", "0")
    assert should_run_standalone_outbox_worker() is False
    assert should_run_standalone_billing_worker() is False


def test_standalone_worker_loops_do_not_run_in_web(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTANCE_ROLE", InstanceRole.WEB.value)
    assert get_instance_role() == InstanceRole.WEB
    assert should_run_standalone_outbox_worker() is False
    assert should_run_standalone_billing_worker() is False
