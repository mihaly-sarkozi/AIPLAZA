# backend/core/kernel/events/event_payload.py
# Feladat: Outbox esemény payloadok közös metadata gazdagítását végzi. Hozzáadja az aktuális observability contextet, tenant adatokat, user/request azonosítókat és instance role-t, hogy a worker processben is visszakövethető legyen az esemény eredete. Az event_channel használja, ezért belső core event helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.kernel.logging.observability import get_observability_context
from core.kernel.runtime.instance_role import get_instance_role


def enrich_event_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    enriched_payload = dict(payload or {})
    meta = dict(enriched_payload.get("_meta") or {})
    current_context = get_observability_context()
    meta.setdefault("correlation_id", current_context.get("correlation_id"))
    meta.setdefault("request_id", current_context.get("request_id"))
    meta.setdefault("tenant_id", current_context.get("tenant_id"))
    meta.setdefault("tenant_slug", current_context.get("tenant_slug") or current_tenant_schema.get(None))
    meta.setdefault("user_id", current_context.get("user_id"))
    meta.setdefault("event_name", event_type)
    try:
        meta.setdefault("instance_role", get_instance_role().value)
    except Exception:
        meta.setdefault("instance_role", None)
    enriched_payload["_meta"] = meta
    return enriched_payload


__all__ = ["enrich_event_payload"]
