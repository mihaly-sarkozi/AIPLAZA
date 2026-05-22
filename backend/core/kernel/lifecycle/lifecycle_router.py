# backend/core/kernel/lifecycle/lifecycle_router.py
# Feladat: A lifecycle és metrics HTTP API FastAPI adaptere. Publikálja a `/health`, `/health/live`, `/health/ready`, root `/livez`, root `/readyz`, `/metrics` és `/platform/lifecycle` endpointokat; readiness esetén 503-at állít. Kernel router a LifecycleService és a Prometheus renderer fölött.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from core.kernel.config.config_loader import get_app_env
from core.kernel.config.config_loader import settings
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.service.audit_service import AuditService
from core.kernel.config.environment import is_production_env
from core.kernel.deps.facade import get_audit_service, service_dependency
from core.kernel.interface.keys import PLATFORM_LIFECYCLE_SERVICE
from core.kernel.lifecycle.health_response import HealthResponse
from core.kernel.lifecycle.lifecycle_service import LifecycleService
from core.kernel.lifecycle.lifecycle_status_response import LifecycleStatusResponse
from core.kernel.lifecycle.liveness_response import LivenessResponse
from core.kernel.lifecycle.outbox_snapshot_response import OutboxSnapshotResponse
from core.kernel.lifecycle.readiness_response import ReadinessResponse
from core.kernel.logging.observability import render_prometheus_metrics
from core.kernel.security.rate_limit import limiter

get_lifecycle_service = service_dependency(PLATFORM_LIFECYCLE_SERVICE)

router = APIRouter()
root_probe_router = APIRouter()


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
    if not is_production_env(env):
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


def _client_ip(request: Request) -> str | None:
    return str(getattr(getattr(request, "client", None), "host", "") or "").strip() or None


def _user_agent(request: Request) -> str | None:
    return str(request.headers.get("user-agent") or "").strip() or None


def require_internal_admin(
    request: Request,
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    supplied_token = _resolve_supplied_token(x_metrics_token, authorization)
    allowed = _is_metrics_request_authorized(request, supplied_token)
    try:
        audit.log(
            AuditLogAction.INTERNAL_ENDPOINT_ACCESSED,
            actor_type="service" if supplied_token else "anonymous",
            outcome="success" if allowed else "failure",
            target_type="internal_endpoint",
            target_id=str(request.url.path),
            details={
                "path": str(request.url.path),
                "method": request.method,
                "authorized": allowed,
            },
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception:
        # Az audit backend hibája ne tegye elérhetőbbé és ne törje a health védelmet.
        pass
    if not allowed:
        raise HTTPException(status_code=404, detail="404")


def _should_return_unhealthy_status(readiness: ReadinessResponse) -> bool:
    status = str(readiness.status or "").strip().lower()
    if status == "not_ready":
        return True
    if status == "degraded":
        try:
            env = get_app_env()
        except Exception:
            env = "dev"
        return is_production_env(env)
    return False


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


@router.get("/livez", response_model=LivenessResponse)
def get_livez(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.liveness()


@router.get("/health/ready", response_model=ReadinessResponse)
def get_readiness(
    response: Response,
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    readiness = svc.readiness()
    if _should_return_unhealthy_status(readiness):
        response.status_code = 503
    return readiness


@router.get("/readyz", response_model=ReadinessResponse)
def get_readyz(
    response: Response,
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    readiness = svc.readiness()
    if _should_return_unhealthy_status(readiness):
        response.status_code = 503
    return readiness


root_probe_router.add_api_route("/livez", get_livez, methods=["GET"], response_model=LivenessResponse)
root_probe_router.add_api_route("/readyz", get_readyz, methods=["GET"], response_model=ReadinessResponse)


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


@router.get("/internal/health/outbox", response_model=OutboxSnapshotResponse)
@limiter.limit("30/minute")
def get_outbox_snapshot(
    request: Request,
    _internal_admin: None = Depends(require_internal_admin),
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.outbox_snapshot()
