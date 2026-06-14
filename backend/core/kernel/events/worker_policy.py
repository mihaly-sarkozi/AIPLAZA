# backend/core/kernel/events/worker_policy.py
# Feladat: Outbox worker production policy helper-eket tartalmaz. Event típusonként eltérő handler timeoutot, lease időtartamot és heartbeat periódust ad, hogy a rövid audit/email események és a hosszú knowledge ingest/index jobok ne ugyanazzal az időlimittel fussanak. Core worker operációs policy modul.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EventWorkerPolicy:
    handler_timeout_seconds: int
    lease_seconds: int
    heartbeat_interval_seconds: int
    execution_mode: Literal["thread"] = "thread"


_DEFAULT_POLICY = EventWorkerPolicy(
    handler_timeout_seconds=15,
    lease_seconds=300,
    heartbeat_interval_seconds=30,
    execution_mode="thread",
)

_EVENT_POLICIES: dict[str, EventWorkerPolicy] = {
    "security.audit_event": EventWorkerPolicy(15, 60, 10, "thread"),
    "email.notification": EventWorkerPolicy(30, 120, 15, "thread"),
    "email_2fa": EventWorkerPolicy(30, 120, 15, "thread"),
    "email_invite": EventWorkerPolicy(30, 120, 15, "thread"),
    # Hosszu furasu knowledge jobok kulon timeout/lease policy-t kapnak.
    # Ez nem per-event process executor: a production izolacio a standalone worker process.
    "knowledge.ingest_pipeline": EventWorkerPolicy(30 * 60, 35 * 60, 30, "thread"),
    "knowledge.index_build": EventWorkerPolicy(60 * 60, 65 * 60, 60, "thread"),
    "knowledge.ingest_item_reprocess": EventWorkerPolicy(30 * 60, 35 * 60, 30, "thread"),
    "knowledge.recovery_sweep": EventWorkerPolicy(10 * 60, 12 * 60, 30, "thread"),
    "kb.discovery_requested": EventWorkerPolicy(30 * 60, 35 * 60, 30, "thread"),
    "kb.embedding_requested": EventWorkerPolicy(30 * 60, 35 * 60, 30, "thread"),
    "kb.indexing_requested": EventWorkerPolicy(60 * 60, 65 * 60, 60, "thread"),
    "url.fetch": EventWorkerPolicy(120, 180, 15, "thread"),
    "file.parse": EventWorkerPolicy(10 * 60, 12 * 60, 30, "thread"),
}


def worker_policy_for_event(event_type: str, *, default_timeout_seconds: int) -> EventWorkerPolicy:
    default_timeout = max(1, int(default_timeout_seconds))
    policy = _EVENT_POLICIES.get(str(event_type or "").strip())
    if policy is None:
        return EventWorkerPolicy(
            handler_timeout_seconds=default_timeout,
            lease_seconds=max(_DEFAULT_POLICY.lease_seconds, default_timeout + 60),
            heartbeat_interval_seconds=_DEFAULT_POLICY.heartbeat_interval_seconds,
            execution_mode=_DEFAULT_POLICY.execution_mode,
        )
    return EventWorkerPolicy(
        handler_timeout_seconds=max(1, int(policy.handler_timeout_seconds)),
        lease_seconds=max(int(policy.lease_seconds), int(policy.handler_timeout_seconds) + 30),
        heartbeat_interval_seconds=max(5, int(policy.heartbeat_interval_seconds)),
        execution_mode="thread",
    )


__all__ = ["EventWorkerPolicy", "worker_policy_for_event"]
