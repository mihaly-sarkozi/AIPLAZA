from __future__ import annotations


def initialize_tenant_state(scope) -> dict:
    state = scope.setdefault("state", {})
    state["tenant_id"] = None
    state["tenant_slug"] = None
    state["tenant_security_version"] = 0
    state["tenant_status"] = None
    state["tenant_config"] = None
    state["tenant_domain"] = None
    state["tenant_snapshot"] = None
    return state


def apply_tenant_snapshot(state: dict, snapshot) -> None:
    state["tenant_id"] = snapshot.tenant_id
    state["tenant_slug"] = snapshot.slug
    state["tenant_security_version"] = snapshot.security_version
    state["tenant_status"] = snapshot.status
    state["tenant_config"] = snapshot.config
    state["tenant_domain"] = snapshot.domain
    state["tenant_snapshot"] = snapshot
