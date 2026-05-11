from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from core.kernel.config.config_loader import settings
from core.kernel.config.environment import get_app_env
from core.kernel.logging.observability import render_prometheus_metrics
from core.di import service_dependency
from core.platform.lifecycle.dto import (
    HealthResponse,
    LifecycleStatusResponse,
    LivenessResponse,
    ReadinessResponse,
)
from core.platform.lifecycle.services import LifecycleService
from core.platform.service_keys import PLATFORM_LIFECYCLE_SERVICE

get_lifecycle_service = service_dependency(PLATFORM_LIFECYCLE_SERVICE)

router = APIRouter()


def _metrics_allowed_ip_set() -> set[str]:
    raw = str(getattr(settings, "metrics_allowed_ips", "") or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _is_metrics_request_authorized(request: Request, supplied_token: str | None) -> bool:
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if env != "prod":
        return True

    if bool(getattr(settings, "metrics_require_ip_allowlist_in_prod", True)):
        remote_ip = str(getattr(getattr(request, "client", None), "host", "") or "").strip()
        allowed_ips = _metrics_allowed_ip_set()
        if not remote_ip or remote_ip not in allowed_ips:
            return False

    if bool(getattr(settings, "metrics_require_token_in_prod", True)):
        expected = str(getattr(settings, "metrics_access_token", "") or "").strip()
        if not expected:
            return False
        provided = str(supplied_token or "").strip()
        if not provided or not secrets.compare_digest(provided, expected):
            return False

    return True


def _resolve_supplied_token(
    x_metrics_token: str | None,
    authorization: str | None,
) -> str | None:
    supplied_token = x_metrics_token
    auth_header = str(authorization or "").strip()
    if not supplied_token and auth_header.lower().startswith("bearer "):
        supplied_token = auth_header[7:].strip()
    return supplied_token


@router.get("/health", response_model=HealthResponse)
def get_health(
    response: Response,
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    health = svc.health()
    if health.status != "ok":
        response.status_code = 503
    return health


@router.get("/health/live", response_model=LivenessResponse)
def get_liveness(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.liveness()


@router.get("/health/ready", response_model=ReadinessResponse)
def get_readiness(
    response: Response,
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    readiness = svc.readiness()
    if readiness.status != "ready":
        response.status_code = 503
    return readiness


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics(
    request: Request,
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    supplied_token = _resolve_supplied_token(x_metrics_token, authorization)
    if not _is_metrics_request_authorized(request, supplied_token):
        # Ne áruljunk el részleteket nyílt internet felé.
        raise HTTPException(status_code=404, detail="404")
    return PlainTextResponse(
        render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/platform/lifecycle", response_model=LifecycleStatusResponse)
def get_lifecycle_status(
    request: Request,
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    supplied_token = _resolve_supplied_token(x_metrics_token, authorization)
    if not _is_metrics_request_authorized(request, supplied_token):
        raise HTTPException(status_code=404, detail="404")
    return svc.runtime_status()
