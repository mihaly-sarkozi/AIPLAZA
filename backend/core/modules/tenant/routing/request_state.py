# backend/core/modules/tenant/routing/request_state.py
# Feladat: Request state helper függvények a tenant contexthez. Feloldott tenant adatokat ír és olvas a FastAPI/Starlette request.state objektumon. Tenant HTTP request integration helper.
# Sárközi Mihály - 2026.05.21

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
