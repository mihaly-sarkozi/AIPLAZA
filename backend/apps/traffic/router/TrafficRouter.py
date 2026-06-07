# backend/apps/traffic/router/TrafficRouter.py
# Feladat: A traffic app FastAPI route definícióit tartalmazza. Jogosultságot ellenőriz, majd a TrafficService read-only overview válaszát adja vissza.

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.traffic.bootstrap.service_keys import TRAFFIC_SERVICE
from apps.traffic.schemas.TrafficOverviewResponse import TrafficOverviewResponse
from core.kernel.deps.facade import service_dependency
from core.kernel.http.tenant_dependencies import RequestTenantContext, require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.users.domain.dto import User


router = APIRouter()
get_traffic_service = service_dependency(TRAFFIC_SERVICE)


def _require_owner_or_admin(user: User) -> None:
    """A forgalom oldal csak owner/admin szerepkörnek látható, user szerepkörnek nem."""

    if str(user.role or "").strip().lower() not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Traffic overview requires owner or admin role")


@router.get("/traffic/overview", response_model=TrafficOverviewResponse)
@limiter.limit("30/minute")
def get_traffic_overview(
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: Any = Depends(get_traffic_service),
    current_user: User = Depends(require_permission("traffic.read")),
) -> TrafficOverviewResponse:
    """Visszaadja a tenant aktuális forgalmi overview-ját frontend kirajzoláshoz."""

    _require_owner_or_admin(current_user)
    return svc.get_overview(tenant)


__all__ = ["get_traffic_service", "router"]
